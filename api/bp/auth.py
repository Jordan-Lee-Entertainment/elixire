from sanic import Blueprint
from sanic import response

from ..common import TokenType
from ..common.auth import login_user, gen_token, pwd_hash
from ..schema import validate, REVOKE_SCHEMA

bp = Blueprint('auth')


@bp.post('/api/login')
async def login_handler(request):
    """
    Login one user to the service
    receives a json payload with fields "user" and "password".

    returns a timed token
    """
    user = await login_user(request)

    return response.json({
        'token': gen_token(user, TokenType.TIMED),
    })


@bp.post('/api/apikey')
async def apikey_handler(request):
    """
    Generate an API key.

    Those types of tokens are non-timed.
    """
    user = await login_user(request)

    return response.json({
        'api_key': gen_token(user, TokenType.NONTIMED),
    })


@bp.post('/api/revoke')
async def revoke_handler(request):
    """
    Revoke all generated tokens.

    This applies to timed and non-timed tokens.
    """
    payload = validate(request.json, REVOKE_SCHEMA)
    user = await login_user(request)

    # by rehashing the password we change the
    # secret data that is signing the tokens,
    # with that, we invalidate any other token
    # used with the old hash
    user_pwd = payload['password']
    hashed = await pwd_hash(request, user_pwd)

    await request.app.db.execute("""
    UPDATE users
    SET password_hash = $1
    WHERE user_id = $2
    """, hashed, user['user_id'])

    await request.app.storage.invalidate(user['user_id'], 'password_hash')

    return response.json({
        'success': True
    })
