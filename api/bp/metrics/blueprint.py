# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import time

from quart import Blueprint, request, current_app as app
from api.bp.metrics.tasks import second_tasks, hourly_tasks, upload_uniq_task
from drillbit import MetricsManager, MetricsDatabaseConfig

bp = Blueprint("metrics", __name__)
log = logging.getLogger(__name__)


async def create_db():
    """Create InfluxDB database"""
    cfg = app.econfig

    database_config = MetricsDatabaseConfig(
        host=cfg.INFLUX_HOST[0],
        port=cfg.INFLUX_HOST[1],
        database=cfg.METRICS_DATABASE,
        ssl=cfg.INFLUX_SSL,
        auth=bool(cfg.INFLUX_USER),
        username=cfg.INFLUX_USER,
        password=cfg.INFLUX_PASSWORD,
    )

    app.metrics = MetricsManager(
        database_config,
        enabled=cfg.ENABLE_METRICS,
        datapoints_per_call=app.econfig.METRICS_LIMIT[0],
    )
    if not cfg.ENABLE_METRICS:
        log.info("metrics are disabled")
        return

    database_name = app.econfig.METRICS_DATABASE
    log.info("Creating database %r", database_name)
    await app.metrics.influx.create_database(db=database_name)

    app.sched.spawn_periodic(
        app.metrics.tick, [], period=app.econfig.METRICS_LIMIT[1], name="metrics_worker"
    )


def start_tasks():
    """Spawn various metric-related tasks."""
    if not app.econfig.ENABLE_METRICS:
        return

    app.sched.spawn_periodic(second_tasks, [app], period=1, name="metrics:second_tasks")

    app.sched.spawn_periodic(
        hourly_tasks, [app], period=3600, name="metrics:hourly_tasks"
    )

    app.sched.spawn_periodic(
        upload_uniq_task, [app], period=86400, name="metrics:unique_uploads"
    )


async def close_worker():
    app.sched.stop("metrics_worker")
    await app.metrics.flush_all(every=1)


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
        return

    # increase the counter on every response from server
    app.counters.inc("response")

    try:
        # calculate latency to get a response, and submit that to influx
        # this field won't help in the case of network failure
        latency = time.monotonic() - request.start_time

        # submit the metric as milliseconds since it is more tangible in
        # normal scenarios
        await app.metrics.submit("response_latency", latency * 1000)
    except AttributeError:
        pass
