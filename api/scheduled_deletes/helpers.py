# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import List


async def fetch_autodelete_jobs(
    user_id: int, *, page: int, resource_type: str
) -> List[dict]:
    return await app.db.fetch(
        f"""
        SELECT job_id
        FROM violet_jobs
        WHERE queue = 'scheduled_deletes'
          AND args->>0 = $1
        """,
        resource_type,
    )
