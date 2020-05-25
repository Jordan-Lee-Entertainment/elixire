# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from typing import Tuple

from quart import current_app as app
from violet.models import QueueJobContext
from hail import Flake
from violet import JobQueue
from api.models import File, Shorten

log = logging.getLogger(__name__)


class ScheduledDeleteQueue(JobQueue):
    """Scheduled deletions of files by request of the user."""

    name = "scheduled_delete_queue"
    # TODO: make it file_id, shorten_id nullable?
    args = ("resource_type", "resource_id")
    poller_seconds = 8

    @classmethod
    def map_persisted_row(_, row) -> Tuple[str, int]:
        return row["resource_type"], row["resource_id"]

    @classmethod
    async def submit(cls, resource_type: str, resource_id: int, **kwargs) -> Flake:
        return await cls._sched.raw_push(cls, (resource_type, resource_id,), **kwargs)

    @classmethod
    async def handle(cls, ctx: QueueJobContext):
        resource_type: str = ctx.args[0]
        resource_id: int = ctx.args[1]

        assert resource_type in ("file", "shorten")
        log.info("Got %r %d to be deleted", resource_type, resource_id)

        # await app.sched.set_job_state(ctx.job_id, {})

        if resource_type == "file":
            resource = await File.fetch(resource_id)
        elif resource_type == "shorten":
            resource = await Shorten.fetch(resource_id)

        if resource is None:
            return

        ctx.set_start()

        log.info("Resource %r %d successfully deleted", resource_type, resource_id)
        await resource.delete()
