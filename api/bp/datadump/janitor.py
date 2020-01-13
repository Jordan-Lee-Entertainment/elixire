# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import pathlib
import time

from quart import current_app as app

log = logging.getLogger(__name__)


async def dump_janitor() -> None:
    """Main data dump janitor task.

    This checks the dump folder every DUMP_JANITOR_PERIOD amount
    of seconds.

    If there is a file that is more than 6 hours old, it gets deleted.
    """

    dumps = pathlib.Path(app.econfig.DUMP_FOLDER)
    for fpath in dumps.glob("*.zip"):
        fstat = fpath.stat()
        now = time.time()

        # if the current time - the last time of modification
        # is more than 6 hours, we delete.
        file_life = now - fstat.st_mtime

        if file_life > 21600:
            log.info(
                "janitor: cleaning %s since it is more than 6h (life: %ds)",
                fpath,
                file_life,
            )

            fpath.unlink()
        else:
            log.info("Ignoring %s, life %ds < 21600", fpath, file_life)


def start_janitor() -> None:
    """Start dump janitor."""
    app.sched.spawn_periodic(
        dump_janitor,
        [],
        period=app.econfig.DUMP_JANITOR_PERIOD,
        job_id="datadump:janitor",
    )
