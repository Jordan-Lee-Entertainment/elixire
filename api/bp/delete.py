# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, jsonify, request, current_app as app

from api.common import delete_file, delete_shorten
from api.common.auth import token_check, password_check
from api.errors import BadInput, JobExistsError
from api.schema import validate, DELETE_ALL_SCHEMA

from api.common.user import mass_file_delete

bp = Blueprint("files", __name__)
log = logging.getLogger(__name__)


@bp.route("/delete_all", methods=["POST"])
async def delete_all():
    """Delete all files for the user"""
    user_id = await token_check()
    j = validate(await request.get_json(), DELETE_ALL_SCHEMA)

    try:
        password = j["password"]
    except KeyError:
        raise BadInput("password not provided")

    await password_check(user_id, password)

    try:
        # TODO use job queue
        app.sched.spawn(
            mass_file_delete, [user_id, False], job_id=f"delete_files_{user_id}"
        )
    except JobExistsError:
        return (
            jsonify({"error": True, "message": "background task already running"}),
            409,
        )

    return "", 204


@bp.route("/files/<shortname>", methods=["DELETE"])
@bp.route("/files/<shortname>/delete", methods=["GET"])
async def delete_single(shortname):
    """Delete a single file."""
    user_id = await token_check()
    await delete_file(shortname, user_id)
    return "", 204


@bp.route("/shortens/<shorten_name>", methods=["DELETE"])
async def shortendelete_handler(user_id, shorten_name):
    """Invalidate a shorten."""
    user_id = await token_check()
    await delete_shorten(shorten_name, user_id)
    return "", 204
