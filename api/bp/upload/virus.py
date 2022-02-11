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


async def run_scan(ctx):
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """
    if not app.econfig.UPLOAD_SCAN:
        log.warning("Scans are disabled, not scanning this file.")
        return

    scanstart = time.monotonic()
    scanproc = await asyncio.create_subprocess_shell(
        "clamdscan -i -m --no-summary -",
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
    )

    # combine outputs
    out, err = map(
        lambda s: s.decode(), await scanproc.communicate(input=ctx.file.body)
    )
    out = f"{out}{err}"
    scanend = time.monotonic()

    delta = round(scanend - scanstart, 6)
    log.info(f"Scanning {ctx.file.size / 1024 / 1024} MB took {delta} seconds")
    log.debug(f"output of clamdscan: {out}")

    if "OK" not in out:
        # Oops.
        log.warning(f"user id {ctx.user_id} did a dumb")
        await scan_webhook(ctx, out)
        raise BadImage("Image contains a virus.")


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
            log.warning(f"File path {fspath!r} was deleted")

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

    @copy_current_app_context
    async def wrapper_task(scan_function, ctx):
        await scan_function(ctx)

    try:
        await asyncio.wait_for(
            wrapper_task(run_scan, ctx), timeout=app.econfig.SCAN_WAIT_THRESHOLD
        )
        log.info("scan file done")
    except asyncio.TimeoutError:
        # the scan took too long, reschedule it on the background
        log.info(f"Scheduled background scan on {ctx.file.name} ({ctx.shortname})")
        app.loop.create_task(wrapper_task(scan_background, ctx))
