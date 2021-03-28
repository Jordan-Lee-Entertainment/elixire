# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
import os
from typing import Any

from quart import current_app as app
from violet.fail_modes import RaiseErr

from api.common.webhook import scan_webhook
from api.errors import BadImage
from api.models import File
from api.common.utils import Timer

log = logging.getLogger(__name__)

STDIN_CHUNK_SIZE = 16384


async def run_scan(ctx) -> None:
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """

    with Timer() as scan_timer:
        log.debug("running clamdscan")
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

        assert process.stdin.can_write_eof()

        stream = ctx.file.stream
        # copy from stream to process
        chunk = stream.read(STDIN_CHUNK_SIZE)
        while chunk != b"":
            process.stdin.write(chunk)
            await process.stdin.drain()
            chunk = stream.read(STDIN_CHUNK_SIZE)

        process.stdin.write_eof()
        log.debug("waiting for clamdscan")
        await process.wait()
        log.debug("wait ok, read out err")

        # stdout and stderr here are for the webhook, not for parsing
        out = await process.stdout.read()
        err = await process.stderr.read()
        total_out = f"{out}{err}"
        log.debug("output: %r", total_out)

        assert process.returncode is not None

    # from clamdscan:
    # RETURN CODES
    #    0 : No virus found.
    #    1 : Virus(es) found.
    #    2 : An error occurred.

    log.info(
        "Scanning %f MB took %s (return value = %d)",
        ctx.file.size / 1024 / 1024,
        scan_timer,
        process.returncode,
    )

    assert process.returncode in (0, 1, 2)

    if process.returncode == 0:
        return
    elif process.returncode == 1:
        log.warning("user id %d got caught in virus scan", ctx.user_id)
        await scan_webhook(ctx, total_out)
        raise BadImage("Image contains a virus.")
    elif process.returncode == 2:
        log.warning("clamdscan FAILED: %r", total_out)
        raise BadImage(f"clamdscan failed: {total_out}")


async def _delete_file_from_scan(ctx) -> None:
    """
    This is a "wrapper" around File.delete tailored
    for the end result of virus scanning.

    It deletes the file by doing os.remove(), then asks delete_file
    to remove it from the database.
    """

    elixire_file = await File.fetch_by(shortname=ctx.shortname)
    if elixire_file is None:
        log.warning("File %r deleted before virus-triggered deletion", ctx.shortname)
        return

    try:
        if elixire_file.fspath is not None:
            os.remove(elixire_file.fspath)
    except OSError:
        log.warning(
            "File path %r deleted before virus-triggered deletion", elixire_file.fspath
        )

    await elixire_file.delete(full=True)
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
        run_scan, [ctx], name=f"virus_scan:{ctx.file.id}", fail_mode=RaiseErr()
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
