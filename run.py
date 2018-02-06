import logging
import traceback

import asyncpg

from sanic import Sanic
from sanic import response

import api.bp.auth
import api.bp.profile
import api.bp.upload
from api.errors import APIError

import config

app = Sanic()
app.econfig = config

# load blueprints
app.blueprint(api.bp.auth.bp)
app.blueprint(api.bp.profile.bp)
app.blueprint(api.bp.upload.bp)

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


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
    log.info('connecting to db')
    app.db = await asyncpg.create_pool(**config.db)
    log.info('conntected to db')


def main():
    # map the entire frontend
    app.static('/', './frontend/output')
    app.static('/', './frontend/output/index.html')
    app.run(host=config.HOST, port=config.PORT)

if __name__ == '__main__':
    main()
