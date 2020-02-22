# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
import os
import time
from typing import Any

from quart import current_app as app

from api.common import delete_file
from api.common.webhook import scan_webhook
from api.errors import BadImage, APIError

log = logging.getLogger(__name__)


async def run_scan(ctx) -> None:
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """
    # await asyncio.sleep(2)

    # TODO a Timer context manager?
    scan_timestamp_start = time.monotonic()

    process = await asyncio.create_subprocess_shell(
        "clamdscan -i -m --no-summary -",
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
    )

    # if returncode is available before we actually run clamdscan, we have
    # a problem. most likely clamdscan is unavailable
    if process.returncode is not None:
        log.error(
            "return code %d before clamdscan, is it installed?", process.returncode
        )

        out, err = map(lambda s: s.decode(), await process.communicate())
        log.error("output: %r", f"{out}{err}")

        return

    body = ctx.file.stream.getvalue()

    # stdout and stderr here are for the webhook, not for parsing
    out, err = map(lambda s: s.decode(), await process.communicate(input=body))
    total_out = f"{out}{err}"
    log.debug("output: %r", total_out)

    scan_timestamp_end = time.monotonic()

    assert process.returncode is not None

    # from clamdscan:
    # RETURN CODES
    #    0 : No virus found.
    #    1 : Virus(es) found.
    #    2 : An error occurred.

    delta = round(scan_timestamp_end - scan_timestamp_start, 6)
    log.info(
        "Scanning %f MB took %f seconds (retcode %d)",
        ctx.file.size / 1024 / 1024,
        delta,
        process.returncode,
    )

    if process.returncode == 0:
        return
    elif process.returncode == 1:
        log.warning("user id %d got caught in virus scan", ctx.user_id)
        await scan_webhook(ctx, total_out)
        raise BadImage("Image contains a virus.")
    else:
        raise APIError("clamdscan returned unknown error code")


async def _delete_file_from_scan(ctx) -> None:
    """
    This is a "wrapper" around "delete_file()" tailored
    for the end result of virus scanning.

    It deletes the file by doing os.remove(), then asks delete_file
    to remove it from the database.
    """
    fspath = await app.db.fetchval(
        """
        SELECT fspath
        FROM files
        WHERE filename = $1
        """,
        ctx.shortname,
    )

    if fspath is None:
        log.warning(f"File {ctx.shortname} deleted before virus-triggered deletion")

    try:
        if fspath is not None:
            os.remove(fspath)
    except OSError:
        log.warning(f"File path {fspath!r} deleted before virus-triggered deletion")

    await delete_file(None, by_name=ctx.shortname, full_delete=True)
    log.info(f"Deleted file {ctx.shortname} (virus found)")


async def scan_bg_waiter(ctx, scan_task: asyncio.Task) -> Any:
    """Waits for the virus scan task to finish and checks its result."""

    # NOTE should we wait without bounds for the scan task?
    # if we add a timeout=, make sure to check if scan_task has anything
    log.debug("waiting for scan task...")
    _done, pending = await asyncio.wait([scan_task])
    assert not pending

    try:
        return scan_task.result()
    except BadImage:
        await _delete_file_from_scan(ctx)
    except Exception:
        log.exception("error while scanning (from background waiter)")


async def scan_file(ctx) -> Any:
    """Run a scan on a file."""
    if not app.econfig.UPLOAD_SCAN:
        log.warning("Scans are disabled, not scanning this file.")
        return

    task = app.sched.spawn(
        run_scan, [ctx], name=f"virus_scan:{ctx.file.id}", fail_mode="raise_error"
    )

    # if the task is on pending, we return and let it continue in the background
    # if the task completed we .result() it
    _, pending = await asyncio.wait([task], timeout=app.econfig.SCAN_WAIT_THRESHOLD)

    if pending:
        log.info("keeping virus scan in bg for %s (%s)", ctx.file.name, ctx.shortname)

        # we keep a "waiter" task in the background for that scan as well,
        # since we would really want to delete the file if the scan finds a
        # positive.
        app.sched.spawn(
            scan_bg_waiter, [ctx, task], name=f"virus_scan_bg:{ctx.file.id}"
        )
        return

    # from the docs, Task.result() will re-raise any exceptions
    # if the task itself failed with an exception.
    return task.result()
