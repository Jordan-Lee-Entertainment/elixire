import logging
import traceback

import asyncpg
import aiohttp
import aioredis

from sanic import Sanic, exceptions
from sanic import response
from sanic_cors import CORS

import api.bp.auth
import api.bp.profile
import api.bp.upload
import api.bp.files
import api.bp.shorten
import api.bp.fetch
import api.bp.admin

from api.errors import APIError, Ratelimited, Banned, BadInput, FailedAuth
from api.common_auth import token_check
from api.common import ban_webhook, check_bans
from api.ratelimit import RatelimitManager
from api.storage import Storage

import config

app = Sanic()
app.econfig = config

# enable cors on api, images and shortens
CORS(app, resources=[r"/api/*", r"/i/*", r"/s/*"])

# load blueprints
app.blueprint(api.bp.auth.bp)
app.blueprint(api.bp.profile.bp)
app.blueprint(api.bp.upload.bp)
app.blueprint(api.bp.files.bp)
app.blueprint(api.bp.shorten.bp)
app.blueprint(api.bp.fetch.bp)
app.blueprint(api.bp.admin.bp)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def options_handler(request):
    return response.text('ok')


@app.exception(Banned)
async def handle_ban(request, exception):
    scode = exception.status_code
    reason = exception.args[0]

    user_id, user_name = request.headers['X-Context']

    log.warning(f'Banning {user_name} {user_id} with reason {reason!r}')

    period = request.app.econfig.BAN_PERIOD
    await request.app.db.execute(f"""
    INSERT INTO bans (user_id, reason, end_timestamp)
    VALUES ($1, $2, now() + interval '{period}')
    """, user_id, reason)

    await ban_webhook(request.app, user_id, reason, period)
    res = {
        'error': True,
        'code': scode,
        'message': reason,
    }

    res.update(exception.get_payload())
    return response.json(res, status=scode)


@app.exception(APIError)
def handle_api_error(request, exception):
    """
    Handle any kind of application-level raised error.
    """
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
    # how do traceback loge???
    val = traceback.format_exc()
    if 'self._ip' in val:
        return None

    status_code = 500
    if isinstance(exception, (exceptions.NotFound, exceptions.FileNotFound)):
        status_code = 404

    log.exception(f'error in request: {repr(exception)}')
    return response.json({
        'error': True,
        'message': repr(exception)
    }, status=status_code)


async def ip_ratelimit(request):
    # TODO: this, using the cf headers, etc
    pass


@app.middleware('request')
async def global_rl(request):
    # handle global ratelimiting
    if '/api' not in request.url:
        return

    if request.method == 'OPTIONS':
        return

    if any(x in request.url
           for x in ('/api/login', '/api/apikey',
                     '/api/revoke', '/api/domains')):
        # not enable ratelimiting for those routes
        # TODO: use ip_ratelimit
        return

    rtl = request.app.rtl
    storage = request.app.storage

    # process ratelimiting
    user_name, user_id, token = None, None, None
    try:
        # should raise KeyError
        token = request.headers['Authorization']
    except (TypeError, KeyError):
        # no token provided.

        # check if payload makes sense
        if not isinstance(request.json, dict):
            raise BadInput('Current payload is not a dict')

        user_name = request.json.get('user')

    if not user_name and token:
        user_id = await token_check(request)

    if not user_id:
        user_id = await storage.get_uid(user_name)

    if not user_id:
        raise FailedAuth('User not found')

    if not user_name and user_id:
        user_name = await storage.get_username(user_id)

    context = (user_name, user_id)
    print(context)

    # ensure both user_name and user_id exist
    if all(v is None for v in context):
        raise FailedAuth('Can not identify user')

    request.headers['X-Context'] = (user_id, user_name)
    bucket = rtl.get_bucket(user_name)

    # ignore when rtl isnt properly initialized
    # with a global cooldown
    if not bucket:
        return

    await check_bans(request, user_id)

    retry_after = bucket.update_rate_limit()
    if bucket.retries > request.app.econfig.RL_THRESHOLD:
        raise Banned('Reached retry limit on ratelimiting.')

    if retry_after:
        raise Ratelimited('You are being ratelimited.', retry_after)


@app.middleware('response')
async def rl_header_set(request, response):
    if '/api' not in request.url:
        return

    if request.method == 'OPTIONS':
        return

    try:
        _, username = request.headers['x-context']
    except KeyError:
        # we are in deep trouble
        log.warning('Request object does not provide a context')
        username = None
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
async def setup_db(app, loop):
    """Initialize db connection before app start"""
    app.session = aiohttp.ClientSession(loop=loop)

    log.info('connecting to db')
    app.db = await asyncpg.create_pool(**config.db)

    log.info('connecting to redis')
    app.redis = await aioredis.create_redis_pool(
        config.redis,
        minsize=3, maxsize=11,
        loop=loop, encoding='utf-8'
    )

    # start ratelimiting man
    app.rtl = RatelimitManager(app)

    app.storage = Storage(app)


@app.listener('after_server_stop')
async def close_db(app, loop):
    log.info('closing db')
    await app.db.close()

    log.info('closing redis')
    app.redis.close()
    await app.redis.wait_closed()


def main():
    # "fix" CORS.
    routelist = list(app.router.routes_all.keys())
    for uri in list(routelist):
        try:
            app.add_route(options_handler, uri, methods=['OPTIONS'])
        except:
            pass

    # TODO: b2 / s3 support ????
    # app.static('/i', './images')

    if config.ENABLE_FRONTEND:
        app.static('/', './frontend/output')
        app.static('/', './frontend/output/index.html')
    else:
        log.info('Frontend link is disabled.')

    app.run(host=config.HOST, port=config.PORT)

if __name__ == '__main__':
    main()
