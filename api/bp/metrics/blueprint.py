# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import time

from quart import Blueprint, request, current_app as app
from api.bp.metrics.tasks import (
    second_tasks,
    hourly_tasks,
    upload_uniq_task,
)
from api.bp.metrics.compactor import compact_task
from api.bp.metrics.manager import MetricsManager

bp = Blueprint("metrics", __name__)
log = logging.getLogger(__name__)


async def is_consenting(user_id: int) -> bool:
    """Return if a user consented to data processing."""
    return await app.db.fetchval(
        """
    SELECT consented
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )


async def create_db():
    """Create InfluxDB database"""
    app.metrics = MetricsManager(app, app.loop)

    if not app.econfig.ENABLE_METRICS:
        return

    dbname = app.econfig.METRICS_DATABASE

    log.info(f"Creating database {dbname}")
    await app.metrics.influx.create_database(db=dbname)


async def start_tasks():
    """Spawn various metric-related tasks."""
    if not app.econfig.ENABLE_METRICS:
        return

    app.sched.spawn_periodic(second_tasks, every=1)
    app.sched.spawn_periodic(hourly_tasks, every=3600)
    app.sched.spawn_periodic(upload_uniq_task, every=86400)
    app.sched.spawn_periodic(compact_task, every=app.econfig.METRICS_COMPACT_GENERALIZE)


async def close_worker():
    await app.metrics.stop()


@bp.before_app_request
async def on_request():
    if not app.econfig.ENABLE_METRICS:
        return

    # increase the counter on every request
    app.counters.inc("request")

    # so we can measure response latency
    request.start_time = time.monotonic()


@bp.after_app_request
async def on_response(response):
    if not app.econfig.ENABLE_METRICS:
        return response

    # increase the counter on every response from server
    app.counters.inc("response")

    try:
        request.start_time
    except AttributeError:
        return response

    # calculate latency to get a response, and submit that to influx
    # this field won't help in the case of network failure
    latency = time.monotonic() - request.start_time

    # submit the metric as milliseconds since it is more tangible in
    # normal scenarios
    await app.metrics.submit("response_latency", latency * 1000)

    return response
