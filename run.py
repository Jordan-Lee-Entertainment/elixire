import logging

import itsdangerous
import bcrypt
import asyncpg

from sanic import Sanic
from sanic import response

from errors import APIError, BadInput, FailedAuth
from common import TokenType
import config

app = Sanic()
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)


SIGNERS = {
    TokenType.TIMED: itsdangerous.TimestampSigner,
    TokenType.NONTIMED: itsdangerous.Signer,
}


@app.exception(APIError)
def handle_exception(request, exception):
    log.warning(f'API error: {exception!r}')
    return response.json({
        'error': True,
        'message': exception.args[0]
    }, status=exception.status_code)


async def login_user(request):
    """
    Login one user, given its username and password.

    Returns a partial user row.
    """
    try:
        username = request.json['user']
        password = request.json['password']
    except (TypeError, KeyError):
        raise BadInput('bad input')

    user = await request.app.db.fetchrow("""
    SELECT user_id, active, password_hash
    FROM users
    WHERE username = $1
    """, username)

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

    return user


async def token_check(request, wanted_type=None):
    """
    Check if a token is valid.
    By default does not care about the token type.
    """
    token = request.json['token']

    token_type = token.count('.')
    if wanted_type and wanted_type != token_type:
        raise FailedAuth('invalid token type')

    data = token.split('.')
    try:
        user_id = int(data[0])
    except (TypeError, ValueError):
        raise FailedAuth('invalid token format')

    user = await request.app.db.fetchrow("""
    SELECT password_hash, active
    FROM users
    WHERE user_id = $1
    """, user_id)

    if not user:
        raise FailedAuth('unknown user ID')

    if not user['active']:
        raise FailedAuth('inactive user')

    pwdhash = user['password_hash']

    signer = SIGNERS[token_type](pwdhash)
    token = token.encode('utf-8')
    try:
        if token_type == TokenType.NONTIMED:
            signer.unsign(token)
        elif token_type == TokenType.TIMED:
            signer.unsign(token, max_age=config.TIMED_TOKEN_AGE)
        else:
            raise FailedAuth('invalid token type')
    except (itsdangerous.SignatureExpired, itsdangerous.BadSignature):
        raise FailedAuth('invalid or expired token')

    return user_id


def gen_token(user, token_type=TokenType.TIMED):
    signer = SIGNERS[token_type](user['password_hash'])
    uid = bytes(str(user['user_id']), 'utf-8')
    return signer.sign(uid)


@app.post('/api/login')
async def login_handler(request):
    """
    Login one user to elixi.re
    receives a json payload with fields "user" and "password".
    
    returns a timed token
    """
    user = await login_user(request)

    return response.json({
        'token': gen_token(user, TokenType.TIMED),
    })


@app.post('/api/apikey')
async def apikey_handler(request):
    """
    Generate an API key.

    Those types of tokens are non-timed.
    """
    user = await login_user(request)

    return response.json({
        'api_key': gen_token(user, TokenType.NONTIMED),
    })


@app.post('/api/revoke')
async def revoke_handler(request):
    """
    Revoke all generated tokens.

    This applies to timed and non-timed tokens.
    """
    user = await login_user(request)

    # we rerash password and invalidate all other tokens
    user_pwd = request.json['password']
    user_pwd = bytes(user_pwd, 'utf-8')

    future = app.loop.run_in_executor(None,
                                      bcrypt.hashpw,
                                      user_pwd,
                                      bcrypt.gensalt(14))

    hashed = await future

    await request.app.db.execute("""
    UPDATE users
    SET password_hash = $1
    WHERE user_id = $2
    """, hashed.decode('utf-8'), user['user_id'])

    return response.json({
        'ok': True
    })


@app.get('/api/profile')
async def profile_handler(request):
    """
    Get your basic information as a user.
    """
    # by default, token_check won't care which
    # token is it being fed with, it will only check.
    user_id = await token_check(request)
    user = await request.app.db.fetchrow("""
    SELECT *
    FROM users
    WHERE user_id = $1
    """, user_id)

    duser = dict(user)
    duser['user_id'] = str(duser['user_id'])
    duser.pop('password_hash')

    return response.json(duser)


@app.get('/api/limits')
async def limits_handler(request):
    user_id = await token_check(request)

    byte_limit = await request.app.db.fetchval("""
    SELECT blimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    return response.json({
        'limit': byte_limit,
    })


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
