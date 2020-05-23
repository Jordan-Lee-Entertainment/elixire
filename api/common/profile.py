# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Tuple, List

from quart import current_app as app
from asyncpg import Record
from violet import JobState

from api.common.common import gen_shortname
from api.models.user import User


async def fetch_dumps(
    user_id: int, *, current: bool = True, future: bool = False
) -> Optional[List[Record]]:
    """Fetch a list of Violet job records in the datadump queue
    according to the given parameters."""
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
            job_id, name, state, taken_at, internal_state
        FROM datadump_queue
        WHERE
            user_id = $1
        {where}
        LIMIT 1
        """,
        user_id,
    )


def wrap_dump_violet_job_state(job_record: Optional[Record]) -> Optional[dict]:
    """Convert a Violet job record *from the datadump queue* to a dictionary for
    serialization purposes."""
    if job_record is None:
        return None

    if job_record["state"] == JobState.NotTaken:
        # TODO calculate position in queue
        return {"state": "in_queue"}
    elif job_record["state"] == JobState.Taken:
        taken_at = job_record["taken_at"]
        internal_state = job_record["internal_state"]

        return {
            "state": "processing",
            "job_id": job_record["job_id"].hex,
            "start_timestamp": taken_at.isoformat() if taken_at is not None else None,
            "current_id": str(internal_state["current_file_id"]),
            "files_total": internal_state["files_total"],
            "files_done": internal_state["files_done"],
        }

    return {"state": "not_in_queue"}


async def gen_user_shortname(user_id: int, *, table: str = "files") -> Tuple[str, int]:
    """Generate a shortname for a file.

    Checks if the user is in paranoid mode and acts accordingly
    """

    user = await User.fetch(user_id)
    assert user is not None
    shortname_len = 8 if user.settings.paranoid else app.econfig.SHORTNAME_LEN
    return await gen_shortname(shortname_len, table)
