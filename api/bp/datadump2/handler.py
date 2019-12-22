# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import zipfile
import os.path

from typing import Tuple, Optional
from quart import current_app as app


async def open_zipdump(
    user_id: int, *, resume=False
) -> Tuple[zipfile.ZipFile, Optional[str]]:
    """Open the zip file relating to your dump."""
    user_name = await app.db.fetchval(
        """
        SELECT username
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    zip_path = os.path.join(app.econfig.DUMP_FOLDER, f"{user_id}_{user_name}.zip")

    if not resume:
        # we use w instead of x because
        # if the dump already exists we should
        # just overwrite it.
        return (
            zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED),
            user_name,
        )

    return zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED), user_name


async def handler(ctx, user_id: int) -> None:
    state = await app.sched.fetch_job_state(ctx.job_id)
    if not state:
        state = {
            "zip": False,
            "min_file": -1,
            "max_file": -1,
            "cur_file": -1,
            "files_done": 0,
        }
        await app.sched.set_job_state(ctx.job_id, state)

    zipdump, user_name = await open_zipdump(user_id, resume=state["zip"])
    state["zip"] = not state["zip"]
    await app.sched.set_job_state(ctx.job_id, state)

    try:
        if user_name is None:
            return

        # await dump_json(zipdump,user_id)
        # await dump_files(ctx, zipdump, user_id, state)
        # await dispatch_dump(user_id, user_name)
    finally:
        zipdump.close()
