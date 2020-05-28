# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from typing import Tuple, Optional

from quart import current_app as app
from violet.models import QueueJobContext
from hail import Flake
from violet import JobQueue
from api.models import File, Shorten

log = logging.getLogger(__name__)


class ScheduledDeleteQueue(JobQueue):
    """Scheduled deletions of files by request of the user."""

    name = "scheduled_delete_queue"
    args = ("file_id", "shorten_id")
    poller_seconds = 8

    @classmethod
    def map_persisted_row(_, row) -> Tuple[int, int]:
        return row["file_id"], row["shorten_id"]

    @classmethod
    async def submit(
        cls,
        *,
        shorten_id: Optional[int] = None,
        file_id: Optional[int] = None,
        **kwargs
    ) -> Flake:
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
