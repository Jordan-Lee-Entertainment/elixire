# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, jsonify, current_app as app

from api.decorators import auth_route
from api.common.domain import get_domain_public


bp = Blueprint("personal_stats", __name__)
log = logging.getLogger(__name__)


async def _get_counts(table: str, user_id: int, extra: str = "") -> int:
    res = await app.db.fetchval(
        f"""
    SELECT COUNT(*)
    FROM {table}
    WHERE uploader = $1
    {extra}
    """,
        user_id,
    )

    return res or 0


async def get_counts(user_id: int) -> dict:
    """Get count information about a user."""
    total_files = await _get_counts("files", user_id)
    total_shortens = await _get_counts("shortens", user_id)
    total_deleted = await _get_counts("files", user_id, "AND deleted = true")

    total_bytes = (
        await app.db.fetchval(
            """
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    """,
            user_id,
        )
        or 0
    )

    return {
        "total_files": total_files,
        "total_deleted_files": total_deleted,
        "total_bytes": total_bytes,
        "total_shortens": total_shortens,
    }


@bp.get("", strict_slashes=False)
@auth_route
async def personal_stats_handler(user_id):
    """Personal statistics for users."""

    return jsonify(await get_counts(user_id))


@bp.get("/my_domains")
@auth_route
async def personal_domain_stats(user_id):
    """Fetch information about the domains you own."""
    db = app.db

    domain_ids = await db.fetch(
        """
    SELECT domain_id
    FROM domain_owners
    WHERE user_id = $1
    """,
        user_id,
    )

    res = {}

    for row in domain_ids:
        domain_id = row["domain_id"]

        domain_info = await db.fetchrow(
            """
        SELECT domain, official, admin_only, permissions
        FROM domains
        WHERE domain_id = $1
        """,
            domain_id,
        )

        dinfo = dict(domain_info)
        dinfo["cf_enabled"] = False

        public = await get_domain_public(domain_id)
        res[domain_id] = {
            "info": dinfo,
            "stats": public,
        }

    return jsonify(res)
