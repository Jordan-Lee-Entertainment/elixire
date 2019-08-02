# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Dict

from quart import current_app as app

from api.common.utils import int_


async def get_limits(user_id) -> dict:
    """Get a user's limit information."""
    limits = await app.db.fetchrow(
        """
        SELECT blimit, shlimit
        FROM limits
        WHERE user_id = $1
        """,
        user_id,
    )

    # unknown user
    if limits is None:
        return {"limit": None, "used": None, "shortenlimit": None, "shortenused": None}

    bytes_used = await app.db.fetchval(
        """
        SELECT SUM(file_size)
        FROM files
        WHERE uploader = $1
        AND file_id > time_snowflake(now() - interval '7 days')
        """,
        user_id,
    )

    shortens_used = await app.db.fetchval(
        """
        SELECT COUNT(*)
        FROM shortens
        WHERE uploader = $1
        AND shorten_id > time_snowflake(now() - interval '7 days')
        """,
        user_id,
    )

    return {
        "limit": limits["blimit"],
        "used": int_(bytes_used, 0),
        "shortenlimit": limits["shlimit"],
        "shortenused": shortens_used,
    }


async def _get_counts(table: str, user_id: int, extra: str = "") -> int:
    return (
        await app.db.fetchval(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE uploader = $1
            {extra}
            """,
            user_id,
        )
        or 0
    )


async def get_counts(user_id: int) -> Dict[str, int]:
    """Get count information about a user."""
    total_files = await _get_counts("files", user_id)
    total_shortens = await _get_counts("shortens", user_id)
    total_deleted = await _get_counts("files", user_id, "AND deleted = true")

    total_bytes = (
        await app.db.fetchval(
            """
            SELECT SUM(file_size)::bigint
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
