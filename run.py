import logging

import asyncpg
import aiohttp
import aioredis

from sanic import Sanic
from sanic.exceptions import NotFound, FileNotFound
from sanic import response
from sanic_cors import CORS
from aioinflux import InfluxDBClient

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

from api.errors import APIError, Ratelimited, Banned, FailedAuth
from api.common_auth import token_check, get_token
from api.common import VERSION, ban_webhook, check_bans, \
    get_ip_addr, ip_ban_webhook
from api.ratelimit import RatelimitManager
from api.storage import Storage

import config

app = Sanic()
app.econfig = config

# enable cors on api, images and shortens
CORS(app, resources=[r"/api/*", r"/i/*", r"/s/*", r"/t/*"], automatic_options=True)

# load blueprints
app.blueprint(api.bp.auth.bp)
app.blueprint(api.bp.profile.bp)
app.blueprint(api.bp.upload.bp)
app.blueprint(api.bp.files.bp)
app.blueprint(api.bp.shorten.bp)
app.blueprint(api.bp.fetch.bp)
app.blueprint(api.bp.admin.bp)
app.blueprint(api.bp.register.bp)
app.blueprint(api.bp.datadump.bp)
app.blueprint(api.bp.metrics.bp)
app.blueprint(api.bp.personal_stats.bp)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Force IP ratelimiting on those routes, as they
# don't provide an authentication context hint
# from the start.
FORCE_IP_ROUTES = (
    '/api/login',
    '/api/apikey',
    '/api/revoke',
    '/api/domains',
    '/api/hello',
    '/api/register',
    '/api/delete_confirm',

    '/api/reset_password',
    '/api/reset_password_confirm',

    '/api/dump_get',
)

# Enforce IP ratelimit on /s/.
NOT_API_RATELIMIT = (
    '/s/',
)

# Enforce special ratelimit settings
# on /i/ and /t/
SPECIAL_RATELIMITS = {
    '/i/': config.SPECIAL_RATELIMITS.get('/i/', config.IP_RATELIMIT),
    '/t/': config.SPECIAL_RATELIMITS.get('/t/', config.IP_RATELIMIT),
}



async def options_handler(request, *args, **kwargs):
    """Dummy OPTIONS handler for CORS stuff."""
    return response.text('ok')


def check_rtl(request, bucket):
    """Check the ratelimit bucket."""
    retry_after = bucket.update_rate_limit()
    if bucket.retries > request.app.econfig.RL_THRESHOLD:
        raise Banned('Reached retry limit on ratelimiting.')

    if retry_after:
        raise Ratelimited('You are being ratelimited.', retry_after)


async def context_fetch(request, storage, user_name, user_id, token):
    if not user_name and token:
        user_id = await token_check(request)

    if not user_id:
        user_id = await storage.get_uid(user_name)

    if not user_id:
        raise FailedAuth('User not found')

    if not user_name and user_id:
        user_name = await storage.get_username(user_id)

    return user_name, user_id


@app.exception(Banned)
async def handle_ban(request, exception):
    """Handle the Banned exception being raised through a request.

    This takes care of inserting a user ban.
    """
    scode = exception.status_code
    reason = exception.args[0]
    rapp = request.app

    if 'X-Context' not in request.headers:
        # use the IP as banning point
        ip_addr = get_ip_addr(request)

        log.warning(f'Banning ip address {ip_addr} with reason {reason!r}')

        period = rapp.econfig.IP_BAN_PERIOD
        await rapp.db.execute(f"""
        INSERT INTO ip_bans (ip_address, reason, end_timestamp)
        VALUES ($1, $2, now() + interval '{period}')
        """, ip_addr, reason)

        await rapp.storage.raw_invalidate(f'ipban:{ip_addr}')
        await ip_ban_webhook(rapp, ip_addr, f'[ip ban] {reason}', period)
    else:
        user_id, user_name = request.headers['X-Context']

        log.warning(f'Banning {user_name} {user_id} with reason {reason!r}')

        period = app.econfig.BAN_PERIOD
        await rapp.db.execute(f"""
        INSERT INTO bans (user_id, reason, end_timestamp)
        VALUES ($1, $2, now() + interval '{period}')
        """, user_id, reason)

        await rapp.storage.raw_invalidate(f'userban:{user_id}')
        await ban_webhook(rapp, user_id, reason, period)

    # generate our error message to the client.
    res = {
        'error': True,
        'code': scode,
        'message': reason,
    }

    res.update(exception.get_payload())
    return response.json(res, status=scode)


@app.exception(APIError)
def handle_api_error(request, exception):
    """Handle any kind of application-level raised error."""
    log.warning(f'API error: {exception!r}')
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
    status_code = 500

    if isinstance(exception, (NotFound, FileNotFound)):
        status_code = 404
        log.warning(f'File not found: {exception!r}')
    else:
        log.exception(f'Error in request: {exception!r}')

    return response.json({
        'error': True,
        'message': repr(exception)
    }, status=status_code)


@app.middleware('request')
async def global_rl(request):
    # handle global ratelimiting on all routes
    if request.method == 'OPTIONS':
        return

    # ratelimiters
    rtl = request.app.rtl
    ip_rtl = request.app.ip_rtl
    sp_rtl = request.app.sp_rtl

    force_ip = any(x in request.url for x in FORCE_IP_ROUTES)
    is_image = any(x in request.url for x in NOT_API_RATELIMIT)
    ip_addr = get_ip_addr(request)

    # special ratelimit handling (always ip-based)
    for match, rtl in sp_rtl.items():
        if match not in request.url:
            continue

        print(f'SPECIAL RATELIMIT MATCH {match}')

        bucket = rtl.get_bucket(ip_addr)
        if not bucket:
            continue

        await check_bans(request, None)
        return check_rtl(request, bucket)

    # global ip-based ratelimiting
    if force_ip or is_image:
        # use the ip as a bucket to the request
        bucket = ip_rtl.get_bucket(ip_addr)

        if not bucket:
            return

        await check_bans(request, None)
        return check_rtl(request, bucket)

    if '/api' not in request.url:
        return

    # from here onwards, only api ratelimiting (user-based, X-Context, etc)
    storage = request.app.storage

    # process ratelimiting
    user_name, user_id, token = None, None, None
    try:
        # should raise KeyError
        token = get_token(request)
    except (TypeError, KeyError):
        # no token provided.

        # check if payload makes sense
        if not isinstance(request.json, dict):
            raise FailedAuth('Request is not identifable. '
                             'No Authorization header?')

        user_name = request.json.get('user')

    user_name, user_id = await context_fetch(request, storage, user_name,
                                             user_id, token)
    context = (user_name, user_id)

    # ensure both user_name and user_id exist
    if all(v is None for v in context):
        raise FailedAuth('Can not identify user')

    # embed request context inside X-Context
    request.headers['X-Context'] = context
    bucket = rtl.get_bucket(user_name)

    # ignore when rtl isnt properly initialized
    # with a global cooldown
    if not bucket:
        return

    await check_bans(request, user_id)
    return check_rtl(request, bucket)


@app.middleware('response')
async def rl_header_set(request, response):
    """Set ratelimit headers when possible!"""
    if '/api' not in request.url:
        return

    if request.method == 'OPTIONS':
        return

    # TODO: use the ip address instead of X-Context
    # or maybe... we could embed the ip address inside some X-Context-IP
    # or something.

    try:
        _, username = request.headers['x-context']
    except KeyError:
        # No context provided.
        return

    bucket = None
    if username:
        bucket = request.app.rtl.get_bucket(username)

    if bucket:
        response.headers['X-RateLimit-Limit'] = bucket.requests
        response.headers['X-RateLimit-Remaining'] = bucket._tokens
        response.headers['X-RateLimit-Reset'] = bucket._window + bucket.second

    try:
        request.headers.pop('x-context')
    except KeyError:
        pass


@app.listener('before_server_start')
async def setup_db(rapp, loop):
    """Initialize db connection before app start"""
    rapp.session = aiohttp.ClientSession(loop=loop)

    log.info('connecting to db')
    rapp.db = await asyncpg.create_pool(**config.db)

    log.info('connecting to redis')
    rapp.redis = await aioredis.create_redis_pool(
        config.redis,
        minsize=3, maxsize=11,
        loop=loop, encoding='utf-8'
    )

    # custom classes for elixire
    log.info('loading user ratelimit manager')
    rapp.rtl = RatelimitManager(app)

    log.info('loading ip ratelimit manager')
    rapp.ip_rtl = RatelimitManager(app, app.econfig.IP_RATELIMIT)

    # special ratelimit managers
    rapp.sp_rtl = {}
    for key, rtl in SPECIAL_RATELIMITS.items():
        log.info(f'initializing special ratelimit for match: {key}')
        rapp.sp_rtl[key] = RatelimitManager(app, rtl)

    rapp.storage = Storage(app)

    # Tasks for datadump API
    rapp.dump_worker = None
    rapp.janitor_task = None

    # metrics stuff
    rapp.rate_requests = 0
    rapp.rate_response = 0

    rapp.file_upload_counter = 0
    rapp.page_hit_counter = 0

    # InfluxDB comms
    if rapp.econfig.ENABLE_METRICS:
        dbname = rapp.econfig.METRICS_DATABASE

        if rapp.econfig.INFLUXDB_AUTH:
            host, port = rapp.econfig.INFLUX_HOST
            rapp.ifxdb = InfluxDBClient(db=dbname,
                                        host=host, port=port,
                                        ssl=rapp.econfig.INFLUX_SSL,
                                        username=rapp.econfig.INFLUX_USER,
                                        password=rapp.econfig.INFLUX_PASSWORD)
        else:
            rapp.ifxdb = InfluxDBClient(db=rapp.econfig.METRICS_DATABASE)

        rapp.ratetask = None
    else:
        log.info('Metrics are disabled!')


@app.listener('after_server_stop')
async def close_db(rapp, _loop):
    """Close all database connections."""
    log.info('closing db')
    await rapp.db.close()

    log.info('closing redis')
    rapp.redis.close()
    await rapp.redis.wait_closed()


@app.get('/api/hello')
async def test_route(_request):
    return response.json({
        'name': 'elixire',
        'version': VERSION,
    })


def main():
    """Main application entry point."""
    # "fix" CORS.
    routelist = list(app.router.routes_all.keys())
    for uri in list(routelist):
        try:
            app.add_route(options_handler, uri, methods=['OPTIONS'])
        except Exception:
            pass

    # TODO: b2 / s3 support ????
    # app.static('/i', './images')

    if config.ENABLE_FRONTEND:
        app.static('/admin', './admin-panel/dist')
        app.static('/admin', './admin-panel/dist/index.html')

        app.static('/', './frontend/output')
        app.static('/', './frontend/output/index.html')
    else:
        log.info('Frontend link is disabled.')

    app.run(host=config.HOST, port=config.PORT)


if __name__ == '__main__':
    main()
