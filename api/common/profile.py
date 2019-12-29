# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Dict, Optional, Tuple, List

from quart import current_app as app
from asyncpg import Record
from violet import JobState

from api.common.utils import int_
from api.common.common import gen_shortname
from api.models.user import User


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


async def fetch_dumps(
    user_id: int, *, current: bool = True, future: bool = False
) -> Optional[List[Record]]:
    where = {
        (False, False): "",
        (False, True): "scheduled_at >= (now() at time zone 'utc')",
        (True, False): "state = 1",
        (True, True): "state = 1 OR scheduled_at >= (now() at time zone 'utc')",
    }[(current, future)]

    if where:
        where = f"AND {where}"

    return await app.db.fetch(
        f"""
        SELECT
            job_id, state, taken_at, internal_state
        FROM violet_jobs
        WHERE
            queue = 'datadump'
        AND args->0 = $1::bigint::text::jsonb
        {where}
        LIMIT 1
        """,
        user_id,
    )


def wrap_dump_job_state(job_record: Optional[Record]) -> Optional[dict]:
    if job_record is None:
        return None

    if job_record["state"] == JobState.NotTaken:
        # TODO calculate position in queue
        return {"state": "in_queue"}
    elif job_record["state"] == JobState.Taken:
        taken_at = job_record["taken_at"]
        state = job_record["internal_state"]

        return {
            "state": "processing",
            "start_timestamp": taken_at.isoformat() if taken_at is not None else None,
            "current_id": str(state["cur_file"]),
            "files_total": state["files_total"],
            "files_done": state["files_done"],
        }

    return {"state": "not_in_queue"}


async def gen_user_shortname(user_id: int, table: str = "files") -> Tuple[str, int]:
    """Generate a shortname for a file.

    Checks if the user is in paranoid mode and acts accordingly
    """

    user = await User.fetch(user_id)
    shortname_len = 8 if user.paranoid else app.econfig.SHORTNAME_LEN
    return await gen_shortname(shortname_len, table)


async def is_metrics_consenting(user_id: int) -> Optional[bool]:
    """Return if a user consented to data processing."""
    # TODO maybe move to Storage.is_metrics_consenting?
    return await app.db.fetchval(
        """
        SELECT consented
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )
