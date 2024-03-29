# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
import os
import time

from quart import current_app as app
from quart.ctx import copy_current_app_context

from api.common import delete_file
from api.common.webhook import scan_webhook
from api.errors import BadImage

log = logging.getLogger(__name__)


async def _run_scan(ctx):
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """

    scan_start_timestamp = time.monotonic()

    log.debug("running clamdscan")
    process = await asyncio.create_subprocess_shell(
        "clamdscan -i -m --no-summary -",
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
    )

    # if returncode is set before we submit the file bytes, it's possible
    # there is a deeper system problem, likely an unavailable clamdscan.
    #
    # we could still send the entirety of the file and still get an invalid
    # returncode (out of the 0,1,2 range), so we must also verify such values
    # afterwards
    if process.returncode is not None:
        log.error(
            "return code %d before clamdscan, is it installed?", process.returncode
        )

        out, err = map(lambda s: s.decode(), await process.communicate())
        log.error("output: %r", f"{out}{err}")
        return

    log.debug("writing file body to clamdscan")
    with ctx.file.save_file_stream_position:
        buffer_size = 16384
        data = ctx.file.stream.read(buffer_size)
        while data:
            log.debug("write %d byte chunk", len(data))
            process.stdin.write(data)
            await process.stdin.drain()
            data = ctx.file.stream.read(buffer_size)

        process.stdin.write_eof()

    # stdout and stderr here are for the webhook, not for parsing
    out, err = map(lambda s: s.decode(), await process.communicate())
    total_out = f"{out}{err}"
    log.debug("output: %r", total_out)

    scan_end_timestamp = time.monotonic()

    assert process.returncode is not None

    # from clamdscan manual:
    # RETURN CODES
    #    0 : No virus found.
    #    1 : Virus(es) found.
    #    2 : An error occurred.

    log.info(
        "Scanning %.2f MB took %.2fms (return value = %d)",
        ctx.file.size / 1024 / 1024,
        (scan_end_timestamp - scan_start_timestamp),
        process.returncode,
    )

    if process.returncode == 0:
        log.debug("clamdscan said ok")
        return
    elif process.returncode == 1:
        log.warning("user id %d got caught in virus scan", ctx.user_id)
        await scan_webhook(ctx, total_out)
        raise BadImage("Image contains a virus.")
    elif process.returncode == 2:
        log.warning("clamdscan FAILED: %r", total_out)
        raise BadImage(f"clamdscan failed: {total_out}")
    else:
        log.error(
            "clamdscan ERRORED with exit code %d (preserving file), output is %r",
            process.returncode,
            total_out,
        )

        # we let the upload pass on clamdscan errors
        return


async def scan_background(ctx):
    """Run an existing scanning task in the background."""
    try:
        await scan_file(ctx)
    except BadImage:
        # let's nuke this image

        fspath = await app.db.fetchval(
            """
        SELECT fspath
        FROM files
        WHERE filename = $1
        """,
            ctx.shortname,
        )

        if not fspath:
            log.warning(f"File {ctx.shortname} was deleted when scan finished")

        try:
            os.remove(fspath)
        except OSError:
            log.warning(f"File path {fspath!r} was already deleted when scan finished")

        await delete_file(ctx.shortname, None, False)
        log.info(f"Deleted file {ctx.shortname}")
    except Exception:
        log.exception("Error during background scan")
    else:
        log.info("Background scan completed without problems")


async def scan_file(ctx) -> None:
    """Run a scan on a file.

    This function schedules the scanning on the background if it takes too
    long to scan.
    """
    if not app.econfig.UPLOAD_SCAN:
        log.debug("Scans are disabled, not scanning this file.")
        return

    @copy_current_app_context
    async def wrapper_task(scan_function, ctx):
        await scan_function(ctx)

    try:
        await asyncio.wait_for(
            wrapper_task(_run_scan, ctx), timeout=app.econfig.SCAN_WAIT_THRESHOLD
        )
        log.info("scan file done")
    except asyncio.TimeoutError:
        # the scan took too long, reschedule it on the background
        log.info(f"Scheduled background scan on {ctx.file.name} ({ctx.shortname})")
        app.loop.create_task(wrapper_task(scan_background, ctx))
