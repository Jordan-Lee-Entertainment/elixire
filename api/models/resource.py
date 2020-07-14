# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


import logging
from datetime import datetime
from typing import Optional
from typing_extensions import Protocol


from hail import Flake

log = logging.getLogger(__name__)


class Resource(Protocol):
    """Main resource superclass."""

    @staticmethod
    async def _internal_schedule_deletion(
        scheduled_at: datetime,
        *,
        file_id: Optional[int] = None,
        shorten_id: Optional[int] = None
    ) -> Optional[Flake]:
        """Generic implementation for scheduled deletions.

        How this works is that "interface" methods on File and Shorten are shown
        to users of the models, while internally, they call this function.
        """

        # This is a hacky way to prevent circular imports. By keeping them
        # at the function level, it enables the class to be fully evaluated
        # by the compiler first, then do those imports later
        #
        # The efficiency of this has not been measured. Here be dragons.
        from api.scheduled_deletes.queue import ScheduledDeleteQueue

        # only one must be set
        assert file_id or shorten_id
        # .. and not both.
        assert not (file_id and shorten_id)

        # this pleases mypy, compared to {} if X else {}, which tbh,
        # makes sense, as this version is a bit cleaner.
        #
        # no 'else's here since we already assert at least one of them
        # isn't None.
        if file_id:
            kwargs = {"file_id": file_id}
        elif shorten_id:
            kwargs = {"shorten_id": shorten_id}

        job_id = await ScheduledDeleteQueue.submit(**kwargs, scheduled_at=scheduled_at)
        log.debug("Created deletion job %r", job_id)
        return job_id

    async def schedule_deletion(self, scheduled_at: datetime) -> Flake:
        ...
