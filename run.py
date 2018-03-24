import logging
import traceback

import asyncpg
import aiohttp

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

from api.errors import APIError, Ratelimited
from api.common_auth import token_check
from api.ratelimit import RatelimitManager

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


@app.middleware('request')
async def global_rl(request):
    # handle global ratelimiting
    if '/api' not in request.url:
        return

    rtl = request.app.rtl

    # process ratelimiting
    user_name = None
    user_id = None
    try:
        # should raise KeyError
        request.headers['Authorization']

        user_id = await token_check(request)
    except KeyError:
        user_name = request.json.get('username')

    if not user_name:
        user_name = await request.app.db.fetchval("""
        SELECT username
        FROM users
        WHERE user_id=$1
        """, user_id)

    if not user_name:
        raise APIError('No usernames were found.')

    request.headers['X-Username'] = user_name

    bucket = rtl.get_bucket(user_name)
    retry_after = bucket.update_rate_limit()
    if retry_after:
        raise Ratelimited('You are being ratelimited.', retry_after)


@app.middleware('response')
async def rl_header_set(request, response):
    username = request.headers.pop('x-username')
    if not username:
        # we are in deep trouble
        log.error('Request object does not provide a username')
        raise APIError('Request object does not provide username')

    bucket = request.app.rtl.get_bucket(username)

    response.headers['X-RateLimit-Limit'] = bucket.requests
    response.headers['X-RateLimit-Remaining'] = bucket._tokens
    response.headers['X-RateLimit-Reset'] = bucket._window + bucket.second


@app.listener('before_server_start')
async def setup_db(app, loop):
    """Initialize db connection before app start"""
    app.session = aiohttp.ClientSession(loop=loop)

    log.info('connecting to db')
    app.db = await asyncpg.create_pool(**config.db)
    log.info('connected to db')

    # start ratelimiting man
    app.rtl = RatelimitManager(app)


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
