# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

import metomi.isodatetime.parsers as parse
from quart import current_app as app, request
from hail import Flake
from dateutil.relativedelta import relativedelta

from api.scheduled_deletes.queue import ScheduledDeleteQueue
from api.errors import BadInput
from api.models import User

log = logging.getLogger(__name__)


async def fetch_autodelete_jobs(
    user_id: int, *, page: int, resource_type: str
) -> List[dict]:
    return await app.db.fetch(
        f"""
        SELECT job_id
        FROM violet_jobs
        WHERE queue = 'scheduled_deletes'
          AND args->>0 = $1
        """,
        resource_type,
    )


def _to_relativedelta(duration) -> relativedelta:
    """
    Convert metomi's Duration object into a dateutil's relativedelta object.
    """
    fields = ("years", "months", "weeks", "days", "hours", "minutes", "seconds")

    # I'm not supposed to pass None to relativedelta or else it oofs
    kwargs = {}
    for field in fields:
        value = getattr(duration, field)
        if value is not None:
            kwargs[field] = value

    return relativedelta(**kwargs)


def validate_request_duration(*, required: bool = False) -> None:
    duration_str = request.args.get("retention_time")
    if duration_str is None and required:
        raise BadInput("retention_time is a required query argument")
    elif duration_str is None:
        return

    now, scheduled_at = extract_scheduled_timestamp(duration_str)
    if scheduled_at < now:
        raise BadInput("Invalid duration timestamp.")


def extract_scheduled_timestamp(duration_str: str) -> Tuple[datetime, datetime]:
    duration = parse.DurationParser().parse(duration_str)
    now = datetime.utcnow()
    relative_delta = _to_relativedelta(duration)
    return now, now + relative_delta


async def maybe_schedule_deletion(user_id: int, **kwargs) -> Optional[Flake]:
    user = await User.fetch(user_id)
    assert user is not None

    scheduled_at = None

    default_max_retention: Optional[int] = user.settings.default_max_retention
    if default_max_retention is not None:
        scheduled_at = datetime.utcnow() + timedelta(seconds=default_max_retention)

    duration_str: Optional[str] = request.args.get("retention_time")
    if duration_str is not None:
        _, scheduled_at = extract_scheduled_timestamp(duration_str)

    if scheduled_at is None:
        return None

    job_id = await ScheduledDeleteQueue.submit(**kwargs, scheduled_at=scheduled_at)
    log.debug("Created deletion job %r", job_id)
    return job_id
