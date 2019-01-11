# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

import asyncpg
import aiohttp
import aioredis

from sanic import Sanic
from sanic.exceptions import NotFound, FileNotFound
from sanic import response
from sanic_cors import CORS
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
from api.bp.metrics.counters import MetricsCounters
from api.bp.admin.audit_log import AuditLog

import config

app = Sanic()
app.econfig = config

# enable cors on api, images and shortens
CORS(
    app,
    resources=[r"/api/*", r"/i/*", r"/s/*", r"/t/*"],
    automatic_options=True,
    expose_headers=[
        'X-Ratelimit-Scope',
        'X-Ratelimit-Limit',
        'X-Ratelimit-Remaining',
        'X-Ratelimit-Reset'
    ]
)

level = getattr(config, 'LOGGING_LEVEL', 'INFO')
logging.basicConfig(level=level)
logging.getLogger('aioinflux').setLevel(logging.INFO)

if level == 'DEBUG':
    fh = logging.FileHandler('elixire.log')
    fh.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(fh)

log = logging.getLogger(__name__)


def set_blueprints(app_):
    # load blueprints
    app_.blueprint(api.bp.ratelimit.bp)
    app_.blueprint(api.bp.auth.bp)
    app_.blueprint(api.bp.index.bp)
    app_.blueprint(api.bp.profile.bp)
    app_.blueprint(api.bp.upload.bp)
    app_.blueprint(api.bp.files.bp)
    app_.blueprint(api.bp.shorten.bp)
    app_.blueprint(api.bp.fetch.bp)

    # load admin blueprints
    app_.blueprint(api.bp.admin.user_bp)
    app_.blueprint(api.bp.admin.object_bp)
    app_.blueprint(api.bp.admin.domain_bp)
    app_.blueprint(api.bp.admin.misc_bp)
    app_.blueprint(api.bp.admin.settings_bp)

    app_.blueprint(api.bp.register.bp)
    app_.blueprint(api.bp.datadump.bp)
    app_.blueprint(api.bp.personal_stats.bp)
    app_.blueprint(api.bp.d1check.bp)
    app_.blueprint(api.bp.misc.bp)
    app_.blueprint(api.bp.frontend.bp)
    app_.blueprint(api.bp.metrics.bp)



async def options_handler(request, *args, **kwargs):
    """Dummy OPTIONS handler for CORS stuff."""
    return response.text('ok')


async def _handle_ban(request, reason: str):
    rapp = request.app

    if 'ctx' not in request:
        # use the IP as banning point
        ip_addr = get_ip_addr(request)

        log.warning(f'Banning ip address {ip_addr} with reason {reason!r}')

        period = rapp.econfig.IP_BAN_PERIOD
        await rapp.db.execute(f"""
        INSERT INTO ip_bans (ip_address, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{period}')
        """, ip_addr, reason)

        await rapp.storage.raw_invalidate(f'ipban:{ip_addr}')
        await ip_ban_webhook(rapp, ip_addr, f'[ip ban] {reason}', period)
    else:
        user_name, user_id = request['ctx']

        log.warning(f'Banning {user_name} {user_id} with reason {reason!r}')

        period = app.econfig.BAN_PERIOD
        await rapp.db.execute(f"""
        INSERT INTO bans (user_id, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{period}')
        """, user_id, reason)

        await rapp.storage.raw_invalidate(f'userban:{user_id}')
        await ban_webhook(rapp, user_id, reason, period)


@app.exception(Banned)
async def handle_ban(request, exception):
    """Handle the Banned exception being raised through a request.

    This takes care of inserting a user ban.
    """
    scode = exception.status_code
    reason = exception.args[0]

    lock_key = request['ctx'][0] if 'ctx' in request else get_ip_addr(request)
    ban_lock = app.locks['bans'][lock_key]

    # generate error message before anything
    res = {
        'error': True,
        'code': scode,
        'message': reason,
    }

    res.update(exception.get_payload())
    resp = response.json(res, status=scode)

    if ban_lock.locked():
        log.warning('Ban lock already acquired.')
        return resp

    await ban_lock.acquire()

    try:
        # actual ban code is here
        await _handle_ban(request, reason)
    finally:
        ban_lock.release()

    return resp


@app.exception(APIError)
def handle_api_error(request, exception):
    """Handle any kind of application-level raised error."""
    log.warning(f'API error: {exception!r}')

    # api errors count as errors as well
    request.app.counters.inc('error')

    scode = exception.status_code
    res = {
        'error': True,
        'code': scode,
        'message': exception.args[0]
    }

    res.update(exception.get_payload())
    return response.json(res, status=scode)


@app.exception(Exception)
def handle_exception(request, exception):
    """Handle any kind of exception."""
    status_code = 500
    url = request.path

    try:
        status_code = exception.status_code
    except AttributeError:
        pass

    if isinstance(exception, (NotFound, FileNotFound, FileNotFoundError)):
        status_code = 404
        log.warning(f'File not found: {exception!r}')

        if request.app.econfig.ENABLE_FRONTEND:
            # admin panel routes all 404's back to index.
            if url.startswith('/admin'):
                return response.file(
                    './admin-panel/build/index.html')

            return response.file(
                './frontend/output/404.html',
                status=404)
    else:
        log.exception(f'Error in request: {exception!r}')

    request.app.inc('error')

    if status_code == 500:
        request.app.inc('error_ise')

    return response.json({
        'error': True,
        'message': repr(exception)
    }, status=status_code)


@app.listener('before_server_start')
async def setup_db(rapp, loop):
    """Initialize db connection before app start"""
    rapp.sched = JobManager()

    rapp.session = aiohttp.ClientSession(loop=loop)

    log.info('connecting to db')
    rapp.db = await asyncpg.create_pool(**config.db)

    log.info('connecting to redis')
    rapp.redis = await aioredis.create_redis_pool(
        config.redis,
        minsize=3, maxsize=11,
        loop=loop, encoding='utf-8'
    )

    rapp.storage = Storage(app)
    rapp.locks = LockStorage()

    # keep an app-level resolver instead of instantiate
    # on every check_email call
    rapp.resolv = resolver.Resolver()

    # metrics stuff
    rapp.counters = MetricsCounters()

    rapp.audit_log = AuditLog(rapp)


@app.listener('after_server_stop')
async def close_db(rapp, _loop):
    """Close all database connections."""
    log.info('closing db')
    await rapp.db.close()

    log.info('closing redis')
    rapp.redis.close()
    await rapp.redis.wait_closed()

    rapp.sched.stop()
    await rapp.session.close()


# we set blueprints globally
# and after every listener is declared.
set_blueprints(app)


def main():
    """Main application entry point."""
    # "fix" CORS.
    routelist = list(app.router.routes_all.keys())
    for uri in list(routelist):
        try:
            app.add_route(options_handler, uri, methods=['OPTIONS'])
        except Exception:
            pass

    del routelist

    app.static('/humans.txt', './static/humans.txt')
    app.static('/robots.txt', './static/robots.txt')

    app.run(host=config.HOST, port=config.PORT)


if __name__ == '__main__':
    main()
