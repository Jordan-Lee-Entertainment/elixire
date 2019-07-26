# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio

import asyncpg
import aiohttp
import aioredis

# from sanic import Sanic
# from sanic.exceptions import NotFound, FileNotFound
# from sanic import response
# from sanic_cors import CORS

from quart import Quart, jsonify, request

from dns import resolver

import api.bp.auth
import api.bp.profile
import api.bp.upload
import api.bp.files
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

from api.errors import APIError, Banned
from api.common import get_ip_addr
from api.common.utils import LockStorage
from api.storage import Storage
from api.jobs import JobManager
from api.bp.metrics.counters import MetricsCounters
from api.bp.admin.audit_log import AuditLog
from api.common.banning import ban_request

import config

# enable cors on api, images and shortens
# CORS(
#     app,
#     resources=[r"/api/*", r"/i/*", r"/s/*", r"/t/*"],
#     automatic_options=True,
#     expose_headers=[
#         'X-Ratelimit-Scope',
#         'X-Ratelimit-Limit',
#         'X-Ratelimit-Remaining',
#         'X-Ratelimit-Reset'
#     ]
# )

level = getattr(config, 'LOGGING_LEVEL', 'INFO')
logging.basicConfig(level=level)
logging.getLogger('aioinflux').setLevel(logging.INFO)

if level == 'DEBUG':
    fh = logging.FileHandler('elixire.log')
    fh.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(fh)

log = logging.getLogger(__name__)


def make_app() -> Quart:
    """Make a Quart instance."""
    app = Quart(__name__)
    # TODO better config under app.cfg
    app.econfig = config
    return app


def set_blueprints(app_):
    """Set the blueprints on the app."""
    # load blueprints

    blueprints = {
        api.bp.auth.bp: '',
        api.bp.misc.bp: '',
        api.bp.d1check.bp: '',
    }

    for blueprint, api_prefix in blueprints.items():
        route_prefix = f'/api{api_prefix or ""}'

        if api_prefix == -1:
            route_prefix = ''

        app_.register_blueprint(blueprint, url_prefix=route_prefix)

    # TODO those are old sanic blueprints
    #app_.blueprint(api.bp.ratelimit.bp)
    #app_.blueprint(api.bp.index.bp)
    #app_.blueprint(api.bp.profile.bp)
    #app_.blueprint(api.bp.upload.bp)
    #app_.blueprint(api.bp.files.bp)
    #app_.blueprint(api.bp.shorten.bp)
    #app_.blueprint(api.bp.fetch.bp)

    ## load admin blueprints
    #app_.blueprint(api.bp.admin.user_bp)
    #app_.blueprint(api.bp.admin.object_bp)
    #app_.blueprint(api.bp.admin.domain_bp)
    #app_.blueprint(api.bp.admin.misc_bp)
    #app_.blueprint(api.bp.admin.settings_bp)

    #app_.blueprint(api.bp.register.bp)
    #app_.blueprint(api.bp.datadump.bp)
    #app_.blueprint(api.bp.personal_stats.bp)
    #app_.blueprint(api.bp.frontend.bp)
    #app_.blueprint(api.bp.metrics.bp)

    ## meme blueprint
    #app_.blueprint(api.bp.wpadmin.bp)

# blueprints are set at the end of the file after declaration of the main
# handlers
app = make_app()


@app.errorhandler(Banned)
async def handle_ban(err: Banned):
    """Handle the Banned exception being raised."""
    status_code = err.status_code
    reason = err.args[0]

    # we keep a lock since when we have a spam user client its best if we don't
    # spam the underlying webhook.

    # the lock is user-based when possible, fallsback to the IP address being
    # banned.
    lock_key = request['ctx'][0] if 'ctx' in request else get_ip_addr()
    ban_lock = app.locks['bans'][lock_key]

    # generate error message before anything
    res = {
        'error': True,
        'code': status_code,
        'message': reason,
    }

    res.update(err.get_payload())
    resp = jsonify(res)

    if ban_lock.locked():
        log.warning('Ban lock already acquired.')
        return resp, status_code

    async with ban_lock:
        await ban_request(reason)

    return resp, status_code


@app.errorhandler(APIError)
def handle_api_error(err: APIError):
    """Handle any kind of application-level raised error."""
    log.warning(f'API error: {err!r}')

    # api errors count as errors as well
    app.counters.inc('error')

    status_code = err.status_code
    res = {
        'error': True,
        'code': status_code,
        'message': err.args[0]
    }

    res.update(err.get_payload())
    return jsonify(res), status_code


@app.errorhandler(500)
def handle_exception(exception):
    """Handle any kind of exception."""
    status_code = 500
    url = request.path

    try:
        status_code = exception.status_code
    except AttributeError:
        pass

    # TODO maybe remove this code
    #if isinstance(exception, (NotFound, FileNotFound, FileNotFoundError)):
    #    status_code = 404
    #    log.warning(f'File not found: {exception!r}')

    #    if request.app.econfig.ENABLE_FRONTEND:
    #        # admin panel routes all 404's back to index (without a 404).
    #        if url.startswith('/admin'):
    #            return response.file(
    #                './admin-panel/build/index.html')

    #        # if we aren't on /api/, return elixire-fe's 404 page
    #        if not url.startswith('/api'):
    #            return response.file(
    #                './frontend/output/404.html',
    #                status=404)
    #else:
    #    log.exception(f'Error in request: {exception!r}')

    request.app.counters.inc('error')

    if status_code == 500:
        request.app.counters.inc('error_ise')

    return jsonify({
        'error': True,
        'message': repr(exception)
    }), status_code


@app.before_serving
async def app_before_serving():
    app.sched = JobManager()
    app.loop = asyncio.get_event_loop()

    app.session = aiohttp.ClientSession(loop=app.loop)

    log.info('connecting to db')
    app.db = await asyncpg.create_pool(**config.db)

    log.info('connecting to redis')
    app.redis = await aioredis.create_redis_pool(
        config.redis,
        minsize=3, maxsize=11,
        loop=app.loop, encoding='utf-8'
    )

    app.storage = Storage(app)
    app.locks = LockStorage()

    # keep an app-level resolver instead of instantiate
    # on every check_email call
    app.resolv = resolver.Resolver()

    # metrics stuff
    app.counters = MetricsCounters()

    # only give real AuditLog when we are on production
    # a MockAuditLog instance will be in that attribute
    # when running tests. look at tests/conftest.py

    # TODO: maybe we can make a MockMetricsManager so that we
    # don't stress InfluxDB out while running the tests.

    # maybe move this to current_app too?
    if not getattr(app, '_test', False):
        app.audit_log = AuditLog(app)


@app.after_serving
async def close_db():
    """Close all database connections."""
    log.info('closing db')
    await app.db.close()

    log.info('closing redis')
    app.redis.close()
    await app.redis.wait_closed()

    app.sched.stop()
    await app.session.close()


set_blueprints(app)
