# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import time

from quart import Blueprint, request, current_app as app
from aioprometheus import render
from api.bp.metrics.tasks import second_tasks, hourly_tasks, upload_uniq_task
from api.bp.metrics.compactor import compact_task
from api.bp.metrics.manager import MetricsManager

bp = Blueprint("metrics", __name__)
log = logging.getLogger(__name__)


async def create_db():
    """Create InfluxDB database"""
    app.metrics = MetricsManager(app, app.loop)

    if not app.econfig.ENABLE_METRICS:
        return

    dbname = app.econfig.METRICS_DATABASE

    log.info(f"Creating database {dbname}")
    await app.metrics.influx.create_database(db=dbname)


def start_tasks():
    """Spawn various metric-related tasks."""
    if not app.econfig.ENABLE_METRICS:
        return

    app.sched.spawn_periodic(
        second_tasks, [app], period=1, task_id="metrics:second_tasks"
    )

    app.sched.spawn_periodic(
        hourly_tasks, [app], period=3600, task_id="metrics:hourly_tasks"
    )

    app.sched.spawn_periodic(
        upload_uniq_task, [app], period=86400, task_id="metrics:unique_uploads"
    )

    app.sched.spawn_periodic(
        compact_task,
        [app],
        period=app.econfig.METRICS_COMPACT_GENERALIZE,
        task_id="metrics:compactor",
    )


async def close_worker():
    await app.metrics.stop()


@bp.before_app_request
async def on_request():
    if not app.econfig.ENABLE_METRICS:
        return

    app.counters.request.inc({"path": request.path})

    # so we can measure response latency
    request.start_time = time.monotonic()


@bp.after_app_request
async def on_response(response):
    if not app.econfig.ENABLE_METRICS:
        return response

    # increase the counter on every response from server
    app.counters.response.inc({"path": request.path})

    try:
        # calculate latency to get a response, and submit that to influx
        # this field won't help in the case of network failure
        latency = time.monotonic() - request.start_time

        # submit the metric as milliseconds since it is more tangible in
        # normal scenarios
        await app.metrics.submit("response_latency", latency * 1000)
    except AttributeError:
        pass

    return response


@bp.route("/metrics")
async def render_metrics():
    content, http_headers = render(app.registry, [request.headers.get("accept")])
    # resp = Response(content, headers=http_headers)
    # TODO headers
    print(content.decode("utf-8"))
    if content is None:
        return "give accept header pls", 400
    return content.decode("utf-8")
