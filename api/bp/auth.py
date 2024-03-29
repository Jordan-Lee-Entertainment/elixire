# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, jsonify, current_app as app, request

from ..common import TokenType
from ..common.auth import login_user, gen_token, pwd_hash
from ..schema import validate, REVOKE_SCHEMA

bp = Blueprint("auth", __name__)


@bp.post("/login")
async def login_handler():
    """
    Login one user to the service
    receives a json payload with fields 'user' and 'password'.

    returns a timed token
    """
    user = await login_user()

    return jsonify(
        {
            "token": gen_token(user, TokenType.TIMED),
        }
    )


@bp.post("/apikey")
async def apikey_handler():
    """
    Generate an API key.

    Those types of tokens are non-timed.
    """
    user = await login_user()

    return jsonify(
        {
            "api_key": gen_token(user, TokenType.NONTIMED),
        }
    )


@bp.post("/revoke")
async def revoke_handler():
    """
    Revoke all generated tokens.

    This applies to timed and non-timed tokens.
    """
    j = await request.get_json()
    payload = validate(j, REVOKE_SCHEMA)
    user = await login_user()

    # by rehashing the password we change the
    # secret data that is signing the tokens,
    # with that, we invalidate any other token
    # used with the old hash
    user_pwd = payload["password"]
    hashed = await pwd_hash(user_pwd)

    await app.db.execute(
        """
    UPDATE users
    SET password_hash = $1
    WHERE user_id = $2
    """,
        hashed,
        user["user_id"],
    )

    await app.storage.invalidate(user["user_id"], "password_hash")

    return jsonify({"success": True})
