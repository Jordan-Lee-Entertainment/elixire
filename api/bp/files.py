# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, current_app as app, jsonify, request
from quart.ctx import copy_current_app_context

from ..common import delete_file, delete_shorten
from ..common.auth import token_check, password_check
from ..decorators import auth_route
from ..errors import BadInput
from .profile import delete_file_task

bp = Blueprint("files", __name__)
log = logging.getLogger(__name__)


@bp.delete("/delete")
async def delete_handler():
    """Invalidate a file."""
    user_id = await token_check()
    # TODO validation
    j = await request.get_json()
    file_name = str(j["filename"])

    await delete_file(file_name, user_id)

    return jsonify({"success": True})


@bp.post("/delete_all")
@auth_route
async def delete_all(user_id):
    """Delete all files for the user"""

    j = await request.get_json()

    try:
        password = j["password"]
    except KeyError:
        raise BadInput("password not provided")

    await password_check(user_id, password)

    # create task to delete all files in the background
    @copy_current_app_context
    async def _wrap(*args):
        await delete_file_task(*args)

    app.sched.spawn(_wrap(user_id, False), f"delete_files_{user_id}")

    return jsonify(
        {
            "success": True,
        }
    )


@bp.route("/delete/<shortname>", methods=["GET", "DELETE"])
@auth_route
async def delete_single(user_id, shortname):
    await delete_file(shortname, user_id)
    return jsonify({"success": True})


@bp.delete("/shortendelete")
async def shortendelete_handler():
    """Invalidate a shorten."""
    user_id = await token_check()
    j = await request.get_json()
    file_name = str(j["filename"])

    await delete_shorten(file_name, user_id)

    return jsonify({"success": True})
