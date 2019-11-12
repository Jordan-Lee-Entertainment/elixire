# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio
from typing import Tuple

import asyncpg
import aiohttp
import aioredis

import quart
from quart import Quart, jsonify, request, send_file

from dns import resolver

# TODO from api.bp import ...
import api.bp.auth
import api.bp.profile
import api.bp.upload
import api.bp.shorten
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
import api.bp.metrics.blueprint
import api.bp.cors
import api.bp.client
import api.bp.list
import api.bp.delete

from api.errors import APIError, Banned
from api.common import get_ip_addr
from api.common.utils import LockStorage
from api.storage import Storage
from api.jobs import JobManager
from api.bp.metrics.counters import MetricsCounters
from api.bp.admin.audit_log import AuditLog
from api.common.banning import ban_request
from api.mode import ElixireMode

import config

log = logging.getLogger(__name__)


def make_app() -> Quart:
    """Make a Quart instance."""
    app = Quart(__name__)

    # TODO better config under app.cfg. check #112
    app.econfig = config
    app.econfig.REQUIRE_APPROVALS = getattr(app.econfig, "REQUIRE_APPROVALS", True)
    app.mode = ElixireMode()

    level = getattr(config, "LOGGING_LEVEL", "INFO")
    logging.basicConfig(level=level)
    logging.getLogger("aioinflux").setLevel(logging.INFO)

    if level == "DEBUG":
        fhandle = logging.FileHandler("elixire.log")
        fhandle.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(fhandle)

    return app


def set_blueprints(app_):
    """Set the blueprints on the app."""
    # load blueprints

    blueprints = {
        api.bp.cors.bp: -1,
        api.bp.ratelimit.bp: "",
        api.bp.auth.bp: "/auth",
        api.bp.misc.bp: "",
        api.bp.index.bp: "",
        api.bp.profile.bp: "/profile",
        api.bp.d1check.bp: "/d1",
        api.bp.upload.bp: "",
        api.bp.personal_stats.bp: "/stats",
        api.bp.register.bp: "/auth",
        api.bp.list.bp: "",
        api.bp.delete.bp: "",
        api.bp.datadump.bp: "/dump",
        api.bp.admin.user_bp: "/admin/users",
        api.bp.admin.object_bp: "/admin",
        api.bp.admin.domain_bp: "/admin/domains",
        api.bp.admin.settings_bp: "/admin/settings",
        api.bp.admin.misc_bp: "/admin",
        api.bp.shorten.bp: -1,
        api.bp.frontend.bp: -1,
        api.bp.fetch.bp: -1,
        api.bp.wpadmin.bp: -1,
        api.bp.client.bp: -1,
    }

    for blueprint, api_prefix in blueprints.items():
        root_prefixes = ["/api", "/api/v3"]
        route_prefixes = [f'{root}{api_prefix or ""}' for root in root_prefixes]

        if api_prefix == -1:
            route_prefixes = [""]

        log.debug("loading blueprint %r", blueprint.name)
        for route in route_prefixes:
            log.debug("with url_prefix %r", route)
            app_.register_blueprint(blueprint, url_prefix=route)


# blueprints are set at the end of the file after declaration of the main
# handlers
app = make_app()


def _wrap_err_in_json(err: APIError) -> Tuple[quart.wrappers.Response, int]:
    res = {"error": True, "message": err.args[0]}
    res.update(err.get_payload())
    return jsonify(res), err.status_code


@app.errorhandler(Banned)
async def handle_ban(err: Banned):
    """Handle the Banned exception being raised."""
    reason = err.args[0]

    # we keep a lock since when we have a spam user client its best if we don't
    # spam the underlying webhook.

    # the lock is user-based when possible, fallsback to the IP address being
    # banned.
    try:
        lock_key = request.ctx[0]
    except AttributeError:
        lock_key = get_ip_addr()

    ban_lock = app.locks["bans"][lock_key]

    # return value
    ret_val = _wrap_err_in_json(err)

    if ban_lock.locked():
        log.warning("Ban lock already acquired.")
        return ret_val

    async with ban_lock:
        await ban_request(reason)

    return ret_val


@app.errorhandler(APIError)
def handle_api_error(err: APIError):
    """Handle any kind of application-level raised error."""
    log.warning(f"API error: {err!r}")

    # api errors count as errors as well
    app.counters.inc("error")

    return _wrap_err_in_json(err)


@app.errorhandler(404)
async def handle_notfound(_err):
    """Give specific pages/behavior when reaching files that aren't found."""
    has_frontend = app.econfig.ENABLE_FRONTEND

    if has_frontend and request.path.startswith("/admin/"):
        return await send_file("./admin-panel/build/index.html")
    elif request.path.startswith("/api"):
        return "Not Found", 404
    elif has_frontend:
        return (await send_file("./frontend/output/404.html")), 404

    return "Not Found", 404


@app.errorhandler(500)
def handle_exception(exception):
    """Handle any kind of exception."""
    status_code = 500

    try:
        status_code = exception.status_code
    except AttributeError:
        pass

    app.counters.inc("error")

    if status_code == 500:
        app.counters.inc("error_ise")

    return jsonify({"error": True, "message": repr(exception)}), status_code


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

    log.info("connecting to redis")
    app.redis = await aioredis.create_redis_pool(
        config.redis, minsize=3, maxsize=11, loop=app.loop, encoding="utf-8"
    )

    app.storage = Storage(app)
    app.locks = LockStorage()

    # keep an app-level resolver instead of instantiate
    # on every check_email call
    app.resolv = resolver.Resolver()

    # metrics stuff
    app.counters = MetricsCounters()

    api.bp.ratelimit.setup_ratelimits()
    await api.bp.metrics.blueprint.create_db()
    api.bp.metrics.blueprint.start_tasks()

    # only give real AuditLog when we are on production
    # a MockAuditLog instance will be in that attribute
    # when running tests. look at tests/conftest.py

    # TODO: maybe we can make a MockMetricsManager so that we
    # don't stress InfluxDB out while running the tests.

    # maybe move this to current_app too?
    if not getattr(app, "_test", False):
        app.audit_log = AuditLog(app)

    await api.bp.datadump.start_dump_worker_ss()
    await api.bp.cors.setup()


@app.after_serving
async def close_db():
    """Close all database connections."""
    log.info("closing db")
    await app.db.close()

    log.info("closing redis")
    app.redis.close()
    await app.redis.wait_closed()

    app.sched.stop()
    await app.session.close()
    await api.bp.metrics.blueprint.close_worker()


set_blueprints(app)
