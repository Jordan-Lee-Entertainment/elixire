# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from starlette.routing import Route, Router

from api.response import resp_empty
from ..common import TokenType
from ..common.auth import login_user, gen_token, pwd_hash
from ..schema import validate, REVOKE_SCHEMA


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


async def apikey_handler(request):
    """
    Generate an API key.

    Those types of tokens are non-timed.
    """
    user = await login_user(request)

    return response.json({
        'api_key': gen_token(request.app, user, TokenType.NONTIMED),
    })


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

    return resp_empty()


bp = Router([
    Route('/login', endpoint=login_handler, methods=['POST']),
    Route('/apikey', endpoint=apikey_handler, methods=['POST']),
    Route('/revoke', endpoint=revoke_handler, methods=['POST']),
])
