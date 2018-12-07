"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

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
    receives a json payload with fields 'user' and 'password'.

    returns a timed token
    """
    user = await login_user(request)

    return response.json({
        'token': gen_token(request.app, user, TokenType.TIMED),
    })


@bp.post('/api/apikey')
async def apikey_handler(request):
    """
    Generate an API key.

    Those types of tokens are non-timed.
    """
    user = await login_user(request)

    return response.json({
        'api_key': gen_token(request.app, user, TokenType.NONTIMED),
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
