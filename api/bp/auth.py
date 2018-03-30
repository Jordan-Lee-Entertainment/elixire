import bcrypt

from sanic import Blueprint
from sanic import response

from ..common import TokenType
from ..common_auth import login_user, gen_token

bp = Blueprint('auth')


@bp.post('/api/login')
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
    user = await login_user(request)

    # we rerash password and invalidate all other tokens
    user_pwd = request.json['password']
    user_pwd = bytes(user_pwd, 'utf-8')

    future = request.app.loop.run_in_executor(None,
                                              bcrypt.hashpw,
                                              user_pwd,
                                              bcrypt.gensalt(14))

    hashed = await future

    await request.app.db.execute("""
    UPDATE users
    SET password_hash = $1
    WHERE user_id = $2
    """, hashed.decode('utf-8'), user['user_id'])

    await request.app.storage.invalidate(user['user_id'], 'password_hash')

    return response.json({
        'success': True
    })
