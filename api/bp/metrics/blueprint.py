# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import base64
import time

from quart import Blueprint, request, current_app as app
from aioprometheus import render

# from api.bp.metrics.tasks import second_tasks, hourly_tasks, upload_uniq_task
from api.errors import FailedAuth

bp = Blueprint("metrics", __name__)
log = logging.getLogger(__name__)


def start_tasks():
    """Spawn various metric-related tasks."""
    if not app.econfig.ENABLE_METRICS:
        return

    # app.sched.spawn_periodic(
    #     second_tasks, [app], period=1, task_id="metrics:second_tasks"
    # )

    # app.sched.spawn_periodic(
    #     hourly_tasks, [app], period=3600, task_id="metrics:hourly_tasks"
    # )

    # app.sched.spawn_periodic(
    #     upload_uniq_task, [app], period=86400, task_id="metrics:unique_uploads"
    # )

    # app.sched.spawn_periodic(
    #     compact_task,
    #     [app],
    #     period=app.econfig.METRICS_COMPACT_GENERALIZE,
    #     task_id="metrics:compactor",
    # )


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
    labels = {"path": request.path, "status_code": response.status_code}
    app.counters.response.inc(labels)

    try:
        latency = time.monotonic() - request.start_time
        app.counters.response_latency.observe(labels, latency)
    except AttributeError:
        pass

    return response


def try_metrics_auth():
    if not app.econfig.METRICS_MUST_AUTH:
        return

    try:
        auth_value = request.headers["authorization"]
    except KeyError:
        raise FailedAuth("Must provide authentication header")

    auth_value = auth_value.replace("Basic ", "", 1)
    try:
        auth_value = base64.b64decode(auth_value).decode()
        components = auth_value.split(":")
    except ValueError:
        pass

    try:
        user, password = components[0], components[1]
    except ValueError:
        raise FailedAuth("Invalid user/password format")

    if user != app.econfig.METRICS_USER or password != app.econfig.METRICS_PASSWORD:
        raise FailedAuth("Invalid user/password")


@bp.route("/metrics")
async def render_metrics():
    try_metrics_auth()

    content, http_headers = render(app.registry, [request.headers.get("accept")])
    return content.decode("utf-8"), 200, http_headers
