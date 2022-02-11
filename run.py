# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio

import asyncpg
import aiohttp
import aioredis

from quart import Quart, request, send_file

from dns import resolver

import api.bp.auth
import api.bp.profile
import api.bp.shorten
import api.bp.upload
import api.bp.files
import api.bp.cors

import api.bp.fetch
import api.bp.admin

import api.bp.register

import api.bp.datadump

import api.bp.metrics
import api.bp.personal_stats

import api.bp.d1check
import api.bp.wpadmin
import api.bp.misc

import api.bp.index

import api.bp.ratelimit
import api.bp.frontend

from api.errors import APIError, Banned
from api.common import get_ip_addr
from api.common.webhook import ban_webhook, ip_ban_webhook
from api.common.utils import LockStorage
from api.storage import Storage
from api.jobs import JobManager

import api.bp.metrics.blueprint
from api.bp.metrics.counters import MetricsCounters

from api.bp.admin.audit_log import AuditLog

import config

# == HACKY PATCH ==
# this MUST be removed once Hypercorn gets py3.10 support.
from asyncio import start_server as _start_server

asyncio.start_server = lambda *args, loop=None, **kwargs: _start_server(*args, **kwargs)


log = logging.getLogger(__name__)


def make_app() -> Quart:
    """Make a Quart instance."""
    app = Quart(__name__)

    # actual max content length can be better determined by a reverse proxy.
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

    # TODO change config to app.cfg
    # also see https://gitlab.com/elixire/elixire/-/issues/112
    app.econfig = config
    app.econfig.REQUIRE_ACCOUNT_APPROVALS = getattr(
        app.econfig, "REQUIRE_ACCOUNT_APPROVALS", True
    )

    level = getattr(config, "LOGGING_LEVEL", "INFO")
    logging.basicConfig(level=level)
    logging.getLogger("aioinflux").setLevel(logging.INFO)

    if level == "DEBUG":
        fhandle = logging.FileHandler("elixire.log")
        fhandle.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(fhandle)

    return app


def set_blueprints(app_):
    # map blueprints to api routes.
    # this is done so that we can provide both /api and /api/v2 namespaces
    # without having to duplicate everything.
    #
    # None means there's no api prefix for the blueprint, so routes
    # in it will be mapped to the root of the webapp
    blueprints = {
        api.bp.cors.bp: None,
        api.bp.ratelimit.bp: None,
        api.bp.auth.bp: "",
        api.bp.register.bp: "",
        api.bp.profile.bp: "",
        api.bp.misc.bp: "",
        api.bp.shorten.bp: None,
        api.bp.upload.bp: "",
        api.bp.files.bp: "",
        api.bp.index.bp: "",
        api.bp.personal_stats.bp: "/stats",
        api.bp.admin.user_bp: "",
        api.bp.admin.domain_bp: "/admin",
        api.bp.admin.misc_bp: "/admin",
        api.bp.admin.object_bp: "/admin",
        api.bp.admin.settings_bp: "/admin",
        api.bp.fetch.bp: None,
        api.bp.frontend.bp: None,
        api.bp.wpadmin.bp: None,
        api.bp.d1check.bp: "",
        api.bp.datadump.bp: "",
        api.bp.metrics.bp: None,
    }

    for blueprint_object, prefix in blueprints.items():
        root_prefixes = ["/api", "/api/v2"]
        route_prefixes = [f'{root}{prefix or ""}' for root in root_prefixes]

        if prefix is None:
            route_prefixes = [""]

        log.debug(
            "loading blueprint %r with prefixes %r",
            blueprint_object.name,
            route_prefixes,
        )
        for route in route_prefixes:
            app_.register_blueprint(blueprint_object, url_prefix=route)


app = make_app()


async def _handle_ban(lock_key, lock_type: str, reason: str):
    if lock_type == "ip":
        ip_addr = get_ip_addr()
        log.warning(f"Banning ip address {ip_addr} with reason {reason!r}")

        period = app.econfig.IP_BAN_PERIOD
        await app.db.execute(
            f"""
        INSERT INTO ip_bans (ip_address, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{period}')
        """,
            ip_addr,
            reason,
        )

        await app.storage.raw_invalidate(f"ipban:{ip_addr}")
        await ip_ban_webhook(ip_addr, f"[ip ban] {reason}", period)
    else:
        user_name, user_id = request._user
        log.warning(f"Banning {user_name} {user_id} with reason {reason!r}")

        period = app.econfig.BAN_PERIOD
        await app.db.execute(
            f"""
        INSERT INTO bans (user_id, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{period}')
        """,
            user_id,
            reason,
        )

        await app.storage.raw_invalidate(f"userban:{user_id}")
        await ban_webhook(user_id, reason, period)


@app.errorhandler(Banned)
async def handle_ban(exception):
    """Handle the Banned exception being raised through a request.

    This takes care of inserting a user ban.
    """
    scode = exception.status_code
    reason = exception.args[0]

    try:
        _username, lock_key = request._user
        lock_type = "user"
    except AttributeError:
        lock_key = get_ip_addr()
        lock_type = "ip"

    ban_lock = app.locks["bans"][lock_key]

    # generate error message before anything
    res = {
        "error": True,
        "code": scode,
        "message": reason,
    }

    res.update(exception.get_payload())
    resp = (res, scode)

    if ban_lock.locked():
        log.warning("Ban lock already acquired.")
        return resp

    async with ban_lock:
        await _handle_ban(lock_key, lock_type, reason)

    return resp


@app.errorhandler(APIError)
def handle_api_error(exception):
    """Handle any kind of application-level raised error."""
    log.warning(f"API error: {exception!r}")

    # api errors count as errors as well
    app.counters.inc("error")

    scode = exception.status_code
    res = {"error": True, "code": scode, "message": exception.args[0]}

    res.update(exception.get_payload())
    return res, scode


@app.errorhandler(FileNotFoundError)
async def handle_notfound_error(err):
    return await handle_notfound(err)


@app.errorhandler(404)
async def handle_notfound(_err):
    rule = request.url_rule
    if rule is None:
        return "Not found", 404
    path = rule.rule

    # TODO move frontends to nginx

    # admin panel routes all 404's back to index.
    if path.startswith("/admin"):
        return await send_file("./admin-panel/build/index.html")

    return await send_file("./frontend/output/404.html"), 404


@app.errorhandler(500)
def handle_exception(exception):
    """Handle any kind of exception."""
    status_code = 500

    try:
        status_code = exception.status_code
    except AttributeError:
        pass

    log.exception(f"Error in request: {exception!r}")

    app.counters.inc("error")
    if status_code == 500:
        app.counters.inc("error_ise")

    return {"error": True, "message": repr(exception)}, status_code


@app.before_serving
async def app_before_serving():
    try:
        app.loop
    except AttributeError:
        app.loop = asyncio.get_event_loop()

    app.sched = JobManager()

    app.session = aiohttp.ClientSession(loop=app.loop)

    log.info("connecting to db")
    app.db = await asyncpg.create_pool(**config.db)
    await api.bp.cors.setup()

    log.info("connecting to redis")
    app.redis_pool = aioredis.ConnectionPool.from_url(
        config.redis,
        max_connections=11,
        encoding="utf-8",
        decode_responses=True,
    )
    app.redis = aioredis.Redis(connection_pool=app.redis_pool)

    app.storage = Storage(app)
    app.locks = LockStorage()

    # keep an app-level resolver instead of instantiate
    # on every check_email call
    app.resolv = resolver.Resolver()

    api.bp.ratelimit.setup_ratelimits()
    # metrics stuff
    app.counters = MetricsCounters()
    await api.bp.metrics.blueprint.create_db()
    await api.bp.metrics.blueprint.start_tasks()

    # only give real AuditLog when we are on production
    # a MockAuditLog instance will be in that attribute
    # when running tests. look at tests/conftest.py

    # TODO: maybe we can make a MockMetricsManager so that we
    # don't stress InfluxDB out while running the tests.

    app.audit_log = AuditLog()

    api.bp.datadump.start_tasks()


@app.after_serving
async def app_after_serving():
    log.info("closing db")
    await app.db.close()

    log.info("closing redis")
    await app.redis_pool.disconnect()

    app.sched.stop()
    await app.session.close()

    await api.bp.metrics.blueprint.close_worker()


set_blueprints(app)
