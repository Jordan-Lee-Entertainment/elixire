# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, request, jsonify

from api.errors import NotFound, BadInput

from api.common.banning import unban_user, unban_ip, TargetType, get_bans
from api.common.pagination import Pagination

from api.common.auth import token_check, check_admin

log = logging.getLogger(__name__)
bp = Blueprint("admin_bans", __name__)


@bp.route("/")
async def get_bans_handler():
    """Get the bans of a given target."""
    user_id = await token_check()
    await check_admin(user_id, True)

    try:
        target_type = TargetType(request.args.get("target_type"))
    except ValueError:
        raise BadInput("Invalid target_type")

    try:
        target_value = request.args["target_value"]
    except KeyError:
        raise BadInput("target_value is required")

    pagination = Pagination()
    bans = await get_bans(
        target_value,
        target_type=target_type,
        page=pagination.page,
        per_page=pagination.per_page,
    )

    return jsonify(bans)
