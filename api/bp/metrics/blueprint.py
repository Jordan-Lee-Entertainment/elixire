# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import time

from sanic import Blueprint
from api.bp.metrics.tasks import (
    second_tasks,
    hourly_tasks,
    upload_uniq_task,
)
from api.bp.metrics.compactor import compact_task
from api.bp.metrics.manager import MetricsManager

bp = Blueprint("metrics")
log = logging.getLogger(__name__)


async def is_consenting(app, user_id: int) -> bool:
    """Return if a user consented to data processing."""
    return await app.db.fetchval(
        """
    SELECT consented
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )


@bp.listener("before_server_start")
async def create_db(app, loop):
    """Create InfluxDB database"""
    app.metrics = MetricsManager(app, loop)

    if not app.econfig.ENABLE_METRICS:
        return

    dbname = app.econfig.METRICS_DATABASE

    log.info(f"Creating database {dbname}")
    await app.metrics.influx.create_database(db=dbname)


@bp.listener("after_server_start")
async def start_tasks(app, _loop):
    """Spawn various metric-related tasks."""
    if not app.econfig.ENABLE_METRICS:
        return

    app.sched.spawn_periodic(second_tasks, [app], 1)

    app.sched.spawn_periodic(hourly_tasks, [app], 3600)

    app.sched.spawn_periodic(upload_uniq_task, [app], 86400)

    app.sched.spawn_periodic(
        compact_task, [app], app.econfig.METRICS_COMPACT_GENERALIZE
    )


@bp.listener("after_server_stop")
async def close_worker(app, loop):
    await app.metrics.stop()


@bp.middleware("request")
async def on_request(request):
    app = request.app

    if not app.econfig.ENABLE_METRICS:
        return

    # increase the counter on every request
    app.counters.inc("request")

    # so we can measure response latency
    request["start_time"] = time.monotonic()


@bp.middleware("response")
async def on_response(request, response):
    app = request.app

    if not app.econfig.ENABLE_METRICS:
        return

    # increase the counter on every response from server
    app.counters.inc("response")

    try:
        # calculate latency to get a response, and submit that to influx
        # this field won't help in the case of network failure
        latency = time.monotonic() - request["start_time"]

        # submit the metric as milliseconds since it is more tangible in
        # normal scenarios
        await app.metrics.submit("response_latency", latency * 1000)
    except KeyError:
        pass
