# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import List, Tuple

from quart import current_app as app, request
import metomi.isodatetime.parsers as parse
from dateutil.relativedelta import relativedelta

from api.errors import BadInput


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


def validate_request_duration() -> None:
    duration_str = request.args.get("duration")
    if duration_str is None:
        return

    now, scheduled_at = extract_scheduled_timestamp(duration_str)
    if scheduled_at < now:
        raise BadInput("Invalid duration timestamp.")


def extract_scheduled_timestamp(duration_str: str) -> Tuple[datetime, datetime]:
    duration = parse.DurationParser().parse(duration_str)
    now = datetime.utcnow()
    relative_delta = _to_relativedelta(duration)
    return now, now + relative_delta
