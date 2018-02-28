import logging
import traceback

import asyncpg
import aiohttp

from sanic import Sanic
from sanic import response
from sanic_cors import CORS

import api.bp.auth
import api.bp.profile
import api.bp.upload
import api.bp.files
import api.bp.shorten

from api.errors import APIError

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
# TODO: app.blueprint(api.bp.fetch.bp)

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


async def options_handler(request):
    return response.text('ok')


@app.exception(APIError)
def handle_api_error(request, exception):
    """
    Handle any kind of application-level raised error.
    """
    log.warning(f'API error: {exception!r}')
    return response.json({
        'error': True,
        'message': exception.args[0]
    }, status=exception.status_code)


@app.exception(Exception)
def handle_exception(request, exception):
    # how do traceback loge???
    val = traceback.format_exc()
    if 'self._ip' in val:
        return None

    log.exception('error in request')
    return response.json({
        'error': True,
        'message': repr(exception)
    }, status=500)


@app.listener('before_server_start')
async def setup_db(app, loop):
    """Initialize db connection before app start"""
    app.session = aiohttp.ClientSession(loop=loop)

    log.info('connecting to db')
    app.db = await asyncpg.create_pool(**config.db)
    log.info('conntected to db')


def main():
    # "fix" CORS.
    routelist = list(app.router.routes_all.keys())
    for uri in list(routelist):
        try:
            app.add_route(options_handler, uri, methods=['OPTIONS'])
        except:
            pass

    # TODO: b2 / s3 support ????
    app.static('/i', './images')

    if config.ENABLE_FRONTEND:
        app.static('/', './frontend/output')
        app.static('/', './frontend/output/index.html')
    else:
        log.info('Frontend link is disabled.')

    app.run(host=config.HOST, port=config.PORT)

if __name__ == '__main__':
    main()
