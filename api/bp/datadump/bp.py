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
from api.common.pagination import Pagination
from api.models import User

log = logging.getLogger(__name__)
bp = Blueprint("datadump", __name__)


def start():
    if app.econfig.DUMP_ENABLED:
        start_janitor()
    else:
        log.info("data dumps are disabled!")


@bp.route("", methods=["POST"])
async def request_data_dump():
    """Request a data dump."""
    if not app.econfig.DUMP_ENABLED:
        raise FeatureDisabled("Data dumps are disabled in this instance")

    user_id = await token_check()

    jobs = await fetch_dumps(user_id, future=True)
    if jobs:
        raise BadInput("Your data dump is currently being processed or in the queue.")

    job_id = await app.sched.push_queue("datadump", [user_id])
    return {"job_id": job_id}


@bp.route("")
async def list_dumps():
    user_id = await token_check()
    jobs = await fetch_dumps(user_id)

    pagination = Pagination()

    jobs = await app.db.fetch(
        """
        SELECT
            job_id, state, inserted_at, taken_at, internal_state,
            COUNT(*) OVER () AS total_count
        FROM violet_jobs
        WHERE
            queue = 'datadump'
        AND args->0 = $3::bigint::text::jsonb
        ORDER BY inserted_at ASC
        LIMIT $2::integer
        OFFSET ($1::integer * $2::integer)
        """,
        pagination.page,
        pagination.per_page,
        user_id,
    )

    total_count = 0 if not jobs else jobs[0]["total_count"]
    return jsonify(
        pagination.response(
            [
                {
                    **dict(r),
                    **{
                        "inserted_at": r["inserted_at"].isoformat(),
                        "taken_at": r["taken_at"].isoformat()
                        if r["taken_at"] is not None
                        else None,
                    },
                }
                for r in jobs
            ],
            total_count=total_count,
        )
    )


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

    user = await User.fetch(user_id)
    filename = f"{user_id}_{user.name}.zip"
    zip_path = os.path.join(app.econfig.DUMP_FOLDER, filename)
    return await send_file(zip_path, as_attachment=True, attachment_filename=filename)
