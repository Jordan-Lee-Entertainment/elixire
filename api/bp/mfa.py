# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, jsonify

# from api.enums import TokenType
# from api.common.auth import login_user, gen_token, pwd_hash
# from api.schema import validate, REVOKE_SCHEMA


bp = Blueprint("mfa", __name__)


@bp.route("/query", methods=["POST"])
async def query():
    # TODO: no users have separate auth methods
    # TODO: if user has auth method like webauthn, create challenge

    # TODO: do not create more than one valid challenge per user, to
    # 	prevent spams from creating just infinite challenges
    return jsonify({"methods": [{"type": "password"}]})
