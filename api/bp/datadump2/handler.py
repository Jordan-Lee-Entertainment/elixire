# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import json
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


def _write_json(zipdump, filepath, obj) -> None:
    objstr = json.dumps(obj, indent=4)
    zipdump.writestr(filepath, objstr)


async def dump_json_data(zipdump, user_id) -> None:
    """Insert user information into the dump."""
    udata = await app.db.fetchrow(
        """
        SELECT user_id, username, active, password_hash, email,
               consented, admin, subdomain, domain
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    _write_json(zipdump, "user_data.json", dict(udata))


async def dump_json_bans(zipdump: zipfile.ZipFile, user_id: int) -> None:
    """Insert user bans, if any, into the dump."""
    bans = await app.db.fetch(
        """
        SELECT user_id, reason, end_timestamp
        FROM bans
        WHERE user_id = $1
        """,
        user_id,
    )

    treated = []
    for row in bans:
        goodrow = {
            "user_id": row["user_id"],
            "reason": row["reason"],
            "end_timestamp": row["end_timestamp"].isoformat(),
        }

        treated.append(goodrow)

    _write_json(zipdump, "bans.json", treated)


async def dump_json_limits(zipdump: zipfile.ZipFile, user_id: int) -> None:
    """Write the current limits for the user in the dump."""
    limits = await app.db.fetchrow(
        """
        SELECT user_id, blimit, shlimit
        FROM limits
        WHERE user_id = $1
        """,
        user_id,
    )

    _write_json(zipdump, "limits.json", dict(limits))


async def dump_json_files(zipdump: zipfile.ZipFile, user_id: int) -> None:
    """Dump all information about the user's files."""
    all_files = await app.db.fetch(
        """
        SELECT file_id, mimetype, filename, file_size, uploader, domain
        FROM files
        WHERE uploader = $1
        """,
        user_id,
    )

    all_files_l = []
    for row in all_files:
        all_files_l.append(dict(row))

    _write_json(zipdump, "files.json", all_files_l)


async def dump_json_shortens(zipdump: zipfile.ZipFile, user_id: int) -> None:
    """Dump all information about the user's shortens."""
    all_shortens = await app.db.fetch(
        """
        SELECT shorten_id, filename, redirto, domain
        FROM shortens
        WHERE uploader = $1
        """,
        user_id,
    )

    all_shortens_l = []
    for row in all_shortens:
        all_shortens_l.append(dict(row))

    _write_json(zipdump, "shortens.json", all_shortens_l)


async def dump_json(zipdump: zipfile.ZipFile, user_id: int) -> None:
    await dump_json_data(zipdump, user_id)
    await dump_json_bans(zipdump, user_id)
    await dump_json_limits(zipdump, user_id)
    await dump_json_files(zipdump, user_id)
    await dump_json_shortens(zipdump, user_id)


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

        await dump_json(zipdump, user_id)
        # await dump_files(ctx, zipdump, user_id, state)
        # await dispatch_dump(user_id, user_name)
    finally:
        zipdump.close()
