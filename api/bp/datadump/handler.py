# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import json
import zipfile
import os.path
import logging

from typing import Tuple, Optional
from quart import current_app as app

from api.common.email import gen_email_token, send_datadump_email
from api.errors import EmailError

log = logging.getLogger(__name__)


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


async def dump_json_user(zipdump, user_id) -> None:
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

    limits = await app.db.fetchrow(
        """
        SELECT blimit AS file_byte_limit, shlimit AS shorten_limit
        FROM limits
        WHERE user_id = $1
        """,
        user_id,
    )

    _write_json(zipdump, "user_data.json", {**dict(udata), **dict(limits)})


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
    await dump_json_user(zipdump, user_id)
    await dump_json_bans(zipdump, user_id)
    await dump_json_files(zipdump, user_id)
    await dump_json_shortens(zipdump, user_id)


async def dump_files(ctx, state: dict, zipdump: zipfile.ZipFile, user_id: int) -> None:
    """Dump files into the data dump zip."""

    current_id = state["cur_file"]
    files_done = state["files_done"]

    # TODO refactor? maybe fetch e.g 10 files in a row instead of
    # one-by-one?

    while True:
        if state["files_done"] % 100 == 0:
            log.info("Worked %d files for user %s", state["files_done"], user_id)

        if current_id is None:
            log.info("Finished file takeout for %s", user_id)
            break

        # add current file to dump
        fdata = await app.db.fetchrow(
            """
            SELECT fspath, filename
            FROM files
            WHERE file_id = $1
            """,
            current_id,
        )

        fspath = fdata["fspath"]
        filename = fdata["filename"]
        ext = os.path.splitext(fspath)[-1]

        filepath = f"./files/{current_id}_{filename}{ext}"
        try:
            await app.loop.run_in_executor(None, zipdump.write, fspath, filepath)
        except FileNotFoundError:
            log.warning("File not found: %s %r", current_id, filename)

        state["files_done"] += 1
        await app.sched.set_job_state(ctx.job_id, state)

        # update current_dump_state
        await app.db.execute(
            """
            UPDATE current_dump_state
            SET current_id = $1, files_done = $2
            WHERE user_id = $3
            """,
            current_id,
            files_done,
            user_id,
        )

        # fetch next id
        current_id = await app.db.fetchval(
            """
            SELECT file_id
            FROM files
            WHERE uploader = $1
              AND file_id > $2
              AND deleted = false
            ORDER BY file_id ASC
            LIMIT 1
            """,
            user_id,
            current_id,
        )
        state["current_id"] = current_id


async def dispatch_dump(user_id: int, user_name: str) -> None:
    """Dispatch the data dump to a user."""
    log.info("dispatching dump for %d %r", user_id, user_name)
    dump_token = await gen_email_token(user_id, "email_dump_tokens")

    await app.db.execute(
        """
        INSERT INTO email_dump_tokens (hash, user_id)
        VALUES ($1, $2)
        """,
        dump_token,
        user_id,
    )

    # either way of email success or failure, we made a datatump, and should
    # not keep worrying about it
    await app.db.execute(
        """
        DELETE FROM current_dump_state
        WHERE user_id = $1
        """,
        user_id,
    )

    try:
        await send_datadump_email(user_id, dump_token)
    except EmailError as exc:
        # TODO make datadump api show errors
        log.warning("failed to send datadump: %r", exc)


async def handler(ctx, user_id: int) -> None:
    state = await app.sched.fetch_job_state(ctx.job_id)
    if not state:
        row = await app.db.fetchrow(
            """
            SELECT MIN(file_id), COUNT(*)
            FROM files
            WHERE uploader = $1
            """,
            user_id,
        )

        state = {
            "zip": False,
            "cur_file": row["min"],
            "files_done": 0,
            "files_total": row["count"],
        }
        await app.sched.set_job_state(ctx.job_id, state)

    log.info(
        "start datadump, resume %s, min %d, total %d",
        state["zip"],
        state["cur_file"],
        state["files_total"],
    )

    zipdump, user_name = await open_zipdump(user_id, resume=state["zip"])

    state["zip"] = not state["zip"]
    await app.sched.set_job_state(ctx.job_id, state)

    try:
        if user_name is None:
            return

        await dump_json(zipdump, user_id)
        await dump_files(ctx, state, zipdump, user_id)
        await dispatch_dump(user_id, user_name)
    finally:
        zipdump.close()
