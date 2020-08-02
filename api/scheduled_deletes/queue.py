# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from typing import Tuple, Optional

from violet.models import QueueJobContext
from hail import Flake
from violet import JobQueue
from api.models import File, Shorten
from api.models.resource import Resource

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
        """Push a file or a shorten to be deleted in the future.

        It is recommended:
         - One of file_id and shorten_id MUST BE passed
         - scheduled_at is passed
        """
        assert shorten_id or file_id
        return await cls._sched.raw_push(cls, (file_id, shorten_id), **kwargs)

    @classmethod
    async def handle(cls, ctx: QueueJobContext):
        file_id: int = ctx.args[0]
        shorten_id: int = ctx.args[1]

        assert file_id or shorten_id

        resource: Optional[Resource] = None
        if file_id is not None:
            log.info("deleting file %d", file_id)
            resource = await File.fetch(file_id)
        elif shorten_id is not None:
            log.info("deleting shorten %d", file_id)
            resource = await Shorten.fetch(shorten_id)

        if resource is None:
            log.info("resource not fonud")
            return

        await resource.delete()
