# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os.path
import logging

from quart import Blueprint, jsonify, request, current_app as app, send_file

from api.errors import BadInput, FeatureDisabled
from api.bp.datadump.janitor import start_janitor
from api.common.auth import token_check, check_admin
from api.common.profile import fetch_dumps

log = logging.getLogger(__name__)
bp = Blueprint("datadump", __name__)


def start():
    if app.econfig.DUMP_ENABLED:
        start_janitor()
    else:
        log.info("data dumps are disabled!")


@bp.route("/request", methods=["POST"])
async def request_data_dump():
    """Request a data dump."""
    if not app.econfig.DUMP_ENABLED:
        raise FeatureDisabled("Data dumps are disabled in this instance")

    user_id = await token_check()

    jobs = await fetch_dumps(user_id, future=True)
    if jobs is not None:
        raise BadInput("Your data dump is currently being processed or in the queue.")

    job_id = await app.sched.push_queue("datadump", [user_id])
    return {"job_id": job_id}


@bp.route("/status")
async def data_dump_user_status():
    """Give information about the current dump for the user,
    if one exists."""
    user_id = await token_check()
    jobs = await fetch_dumps(user_id)

    # TODO structure job.state
    return jsonify(jobs[0]["state"] if jobs else None)


# TODO move to its own admin blueprint?
@bp.route("/admin/status")
async def data_dump_global_status():
    """Only for admins: all stuff related to data dump state."""
    user_id = await token_check()
    await check_admin(user_id, True)

    queue = await app.db.fetch(
        """
        SELECT job_id, args::json->0 AS user_id, inserted_at, scheduled_at
        FROM violet_jobs
        WHERE state = 0
        ORDER BY scheduled_at ASC
        """
    )

    queue = [str(el["user_id"]) for el in queue]

    current = (
        await app.db.fetchrow(
            """
        SELECT job_id, args::json->0 AS user_id, inserted_at, scheduled_at
        FROM violet_jobs
        WHERE state = 1
        """
        )
        or {}
    )

    return jsonify({"queue": queue, "current": dict(current)})


@bp.route("/get")
async def get_dump():
    """Download the dump file."""
    try:
        dump_token = str(request.args["key"])
    except (KeyError, ValueError):
        raise BadInput("No valid key provided.")

    user_id = await app.db.fetchval(
        """
        SELECT user_id
        FROM email_dump_tokens
        WHERE hash = $1 AND now() < expiral
        """,
        dump_token,
    )

    if not user_id:
        raise BadInput("Invalid or expired token.")

    user_name = await app.db.fetchval(
        """
        SELECT username
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    filename = f"{user_id}_{user_name}.zip"
    zip_path = os.path.join(app.econfig.DUMP_FOLDER, filename)
    return await send_file(zip_path, as_attachment=True, attachment_filename=filename)
