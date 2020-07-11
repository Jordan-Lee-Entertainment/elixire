# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


import logging
from datetime import datetime, timedelta
from typing import Optional

from quart import request
from hail import Flake

from api.models import User

log = logging.getLogger(__name__)


class Resource:
    """Main resource superclass."""

    @staticmethod
    async def _internal_schedule_deletion(
        user: User, *, file_id: Optional[int] = None, shorten_id: Optional[int] = None
    ) -> Optional[Flake]:
        """Generic implementation for scheduled deletions.

        How this works is that "interface" methods on File and Shorten are shown
        to users of the models, while internally, they call this function.

        Will check retention_time on the current request's query parameters.
        """

        # This is a hacky way to prevent circular imports. By keeping them
        # at the function level, it enables the class to be fully evaluated
        # by the compiler first, then do those imports later
        #
        # The efficiency of this has not been measured. Here be dragons.
        from api.scheduled_deletes.helpers import extract_scheduled_timestamp
        from api.scheduled_deletes.queue import ScheduledDeleteQueue

        assert user is not None

        # only one must be set
        assert file_id or shorten_id
        # .. and not both.
        assert not (file_id and shorten_id)

        scheduled_at = None

        default_max_retention: Optional[int] = user.settings.default_max_retention
        if default_max_retention is not None:
            scheduled_at = datetime.utcnow() + timedelta(seconds=default_max_retention)

        duration_str: Optional[str] = request.args.get("retention_time")
        if duration_str is not None:
            _, scheduled_at = extract_scheduled_timestamp(duration_str)

        if scheduled_at is None:
            return None

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
