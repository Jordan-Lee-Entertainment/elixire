# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Dict, Optional, Union, Tuple

from quart import current_app as app

from api.common.utils import int_
from api.common.common import gen_shortname


async def get_limits(user_id: int) -> Dict[str, Optional[int]]:
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


async def get_dump_status(user_id: int) -> Dict[str, Union[str, int]]:
    """Get datadump status."""
    row = await app.db.fetchrow(
        """
        SELECT user_id, start_timestamp, current_id, total_files, files_done
        FROM current_dump_state
        WHERE user_id = $1
        """,
        user_id,
    )

    if not row:
        queue = await app.db.fetch(
            """
            SELECT user_id
            FROM dump_queue
            ORDER BY request_timestamp ASC
            """
        )

        queue = [r["user_id"] for r in queue]

        try:
            pos = queue.index(user_id)
            return {"state": "in_queue", "position": pos + 1}
        except ValueError:
            return {"state": "not_in_queue"}

    return {
        "state": "processing",
        "start_timestamp": row["start_timestamp"].isoformat(),
        "current_id": str(row["current_id"]),
        "total_files": row["total_files"],
        "files_done": row["files_done"],
    }


async def is_user_paranoid(user_id: int) -> Optional[bool]:
    """If the user is in paranoid mode."""
    # TODO maybe move to Storage.is_paranoid?
    return await app.db.fetchval(
        """
        SELECT paranoid
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )


async def gen_user_shortname(user_id: int, table: str = "files") -> Tuple[str, int]:
    """Generate a shortname for a file.

    Checks if the user is in paranoid mode and acts accordingly
    """

    paranoid = await is_user_paranoid(user_id)
    shortname_len = 8 if paranoid else app.econfig.SHORTNAME_LEN
    return await gen_shortname(shortname_len, table)
