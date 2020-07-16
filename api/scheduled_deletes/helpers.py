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
    """If retention_time is given in the query arguments, check its validity.

    This helper function exists because input validation should always happen
    before any other input is used.

    Raises BadInput if the value is wrongly formatted, etc.
    """
    duration_str = request.args.get("retention_time")
    if duration_str is None and required:
        raise BadInput("retention_time is a required query argument")
    elif duration_str is None:
        return

    now, scheduled_at = extract_scheduled_timestamp(duration_str)
    if scheduled_at < now:
        raise BadInput("Invalid duration timestamp.")


def extract_scheduled_timestamp(duration_str: str) -> Tuple[datetime, datetime]:
    """From a given duration string, return a tuple with datetimes representing
    the range [now, now + duration]."""

    # The juggling of metomi + dateutil is caused by the poor ISO8601 parsing
    # and ISO8601 parsers having poor integration with datetime.
    #
    # Time APIs kinda suck.

    duration = parse.DurationParser().parse(duration_str)
    now = datetime.utcnow()
    relative_delta = _to_relativedelta(duration)
    return now, now + relative_delta
