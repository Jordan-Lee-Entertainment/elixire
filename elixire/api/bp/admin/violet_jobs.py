# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import Tuple
from quart import Blueprint, jsonify, current_app as app, request
from hail import Flake

from api.common.auth import token_check, check_admin
from api.common.violet_jobs import violet_jobs_to_json
from api.common.utils import fetch_json_rows
from api.errors import BadInput

log = logging.getLogger(__name__)
bp = Blueprint("admin_violet_jobs", __name__)


def _get_before_after() -> Tuple[Flake, Flake, int]:
    try:
        # TODO store this value somewhere in hail, maybe hail.MAX_FLAKE_ID?
        before_str = request.args.get("before", "f" * 32)
        before = Flake.from_string(before_str)
    except ValueError:
        raise BadInput("Optional before parameter must be a valid FlakeID")

    try:
        after_str = request.args.get("after", "0" * 32)
        after = Flake.from_string(after_str)
    except ValueError:
        raise BadInput("Optional after parameter must be a valid FlakeID")

    try:
        limit = int(request.args.get("limit", 100))
        limit = max(1, limit)
        limit = min(100, limit)
    except ValueError:
        limit = 100

    return before, after, limit


@bp.route("")
async def list_jobs():
    """List scheduled jobs in the violet_jobs table.

    This is an introspective way for instance admins to peek at the queues,
    debug, etc.
    """
    before, after, limit = _get_before_after()
    admin_id = await token_check()
    await check_admin(admin_id, True)

    queue = request.args.get("queue")

    args = [] if not queue else [queue]
    queue_where = "AND queue = $4" if queue else ""

    jobs = await fetch_json_rows(
        app.db,
        f"""
        SELECT
            job_id, name, state, errors, inserted_at, taken_at, internal_state,
            COUNT(*) OVER () AS total_count
        FROM violet_jobs
        WHERE job_id > $1
          AND job_id < $2
          {queue_where}
        ORDER BY job_id DESC
        LIMIT $3::integer
        """,
        after.as_uuid,
        before.as_uuid,
        limit,
        *args,
    )

    total_count = 0 if not jobs else jobs[0]["total_count"]
    return jsonify({"results": violet_jobs_to_json(jobs), "total": total_count})
