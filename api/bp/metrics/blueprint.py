# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import time

from quart import Blueprint, request, current_app as app
from api.bp.metrics.tasks import hourly_tasks
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

    # app.sched.spawn_periodic(second_tasks, [app], period=1, name="metrics:second_tasks")

    app.sched.spawn_periodic(
        hourly_tasks, [app], period=3600, name="metrics:hourly_tasks"
    )


async def close_worker():
    log.info("flushing all metrics")
    app.sched.stop("metrics_worker")
    await app.metrics.flush_all(every=1)


def influx_measurement(scope: str = "request", **extra) -> str:
    """Convert the current request (or response) into an InfluxDB measurement."""
    if request.url_rule is None:
        return scope

    path = request.url_rule.rule
    method = request.method

    tags = {"route": f"{method}_{path}"}
    tags.update(extra)
    tags_str: str = ",".join(f"{k}={v}" for k, v in tags.items())

    return f"{scope}{',' + tags_str if tags_str else ''}"


@bp.before_app_request
async def on_request():
    if not app.econfig.ENABLE_METRICS:
        return

    # so we can measure response latency
    request.start_time = time.monotonic()

    # TODO: For now, we can go with this, but once a lot of requests come up,
    # it is likely this code will be a bottleneck
    # for the queue of the metrics manager (drillbit maintains a queue of
    # incoming datapoints from elixire to maintain a steady rate while sending
    # them to influxdb).
    #
    # The best way to approach a fix would be to aggregate per second using
    # MetricsCounters instead of per-request as this snippet of code does.
    full_measurement = influx_measurement()
    await app.metrics.submit(full_measurement, 1)


async def maybe_submit_latency(full_measurement: str):
    try:
        # calculate latency to get a response, and submit that to influx
        # this field won't help in the case of network failure
        latency = time.monotonic() - request.start_time
    except AttributeError:
        return

    # submit the metric as milliseconds since it is more tangible in
    # normal scenarios
    await app.metrics.submit("response_latency", latency * 1000)

    # also submit with the tags
    await app.metrics.submit(full_measurement, latency * 1000)


@bp.after_app_request
async def on_response(response):
    if app.econfig.ENABLE_METRICS:
        full_measurement = influx_measurement("response", status=response.status_code)
        await app.metrics.submit(full_measurement, 1)

        full_measurement_latency = influx_measurement(
            "response_latency", status=response.status_code
        )
        await maybe_submit_latency(full_measurement_latency)

    return response
