import logging

import itsdangerous
import bcrypt
import asyncpg

from sanic import Sanic
from sanic import response

from errors import APIError, BadInput, FailedAuth
import config

app = Sanic()
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


@app.exception(APIError)
def handle_exception(request, exception):
    log.warning(f'API error: {exception!r}')
    return response.json({
        'error': True,
        'message': exception.args[0]
    }, status=exception.status_code)


@app.post('/api/login')
async def login_handler(request):
    """
    Login one user to elixi.re
    receives a json payload with fields "user" and "password".
    
    returns a timed token
    """
    try:
        user = request.json['user']
        password = request.json['password']
    except (TypeError, KeyError):
        raise BadInput('bad input')

    user = await request.app.db.fetchrow("""
    SELECT user_id, active, password_hash
    FROM users
    WHERE username = $1
    """, user)

    if not user:
        raise FailedAuth('user or password invalid')

    if not user['active']:
        raise FailedAuth('user or password invalid')

    # check password validity
    pb = bytes(password, 'utf-8')
    ph = bytes(user['password_hash'], 'utf-8')
    future = app.loop.run_in_executor(None,
                                      bcrypt.checkpw,
                                      pb, ph)

    if not await future:
        raise FailedAuth('user or password invalid')

    # generate timed token
    signer = itsdangerous.TimestampSigner(user['password_hash'])
    uid = bytes(str(user['user_id']), 'utf-8')
    token = signer.sign(uid)

    return response.json({
        'token': token,
    })


@app.post('/api/apikey')
async def apikey_handler(request):
    """
    Generate an API key.

    Those types of tokens are non-timed.
    """
    pass


@app.post('/api/revoke')
async def revoke_handler(request):
    """
    Revoke all generated tokens.

    This applies to timed and non-timed tokens.
    """
    pass

@app.listener('before_server_start')
async def setup_db(app, loop):
    log.info('connecting to db')
    app.db = await asyncpg.create_pool(**config.db)
    log.info('conntected to db')


def main():
    # all static files
    app.static('/static', './static')

    # index page
    app.static('/index.html', './static/index.html')
    app.static('/', './static/index.html')

    app.run(host=config.HOST, port=config.PORT)

if __name__ == '__main__':
    main()
