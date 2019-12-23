# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os.path
import logging
from typing import Optional

from asyncpg import Record
from quart import Blueprint, jsonify, request, current_app as app, send_file

from api.errors import BadInput, FeatureDisabled
from api.bp.datadump2.janitor import start_janitor
from api.common.auth import token_check, check_admin

log = logging.getLogger(__name__)
bp = Blueprint("datadump", __name__)


def start():
    if app.econfig.DUMP_ENABLED:
        start_janitor()
    else:
        log.info("data dumps are disabled!")


async def fetch_dump(
    user_id: int, *, current: bool = True, future: bool = False
) -> Optional[Record]:
    where = {
        (False, False): "",
        (False, True): "scheduled_at >= (now() at time zone 'utc')",
        (True, False): "state = 1",
        (True, True): "state = 1 OR scheduled_at >= (now() at time zone 'utc')",
    }[(current, future)]

    if where:
        where = f"AND {where}"

    return await app.db.fetchrow(
        f"""
        SELECT job_id, internal_state
        FROM violet_jobs
        WHERE
            args->0 = $1::bigint::text::jsonb
        {where}
        LIMIT 1
        """,
        user_id,
    )


@bp.route("/request", methods=["POST"])
async def request_data_dump():
    """Request a data dump."""
    if not app.econfig.DUMP_ENABLED:
        raise FeatureDisabled("Data dumps are disabled in this instance")

    user_id = await token_check()

    job = await fetch_dump(user_id, future=True)
    if job is not None:
        raise BadInput("Your data dump is currently being processed or in the queue.")

    job_id = await app.sched.push_queue("datadump", [user_id])
    return {"job_id": job_id}


@bp.route("/status")
async def data_dump_user_status():
    """Give information about the current dump for the user,
    if one exists."""
    user_id = await token_check()
    job = await fetch_dump(user_id)
    # TODO structure job.state
    return jsonify(job["state"] if job is not None else None)


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

    zip_path = os.path.join(app.econfig.DUMP_FOLDER, f"{user_id}_{user_name}.zip")

    return await send_file(zip_path)
