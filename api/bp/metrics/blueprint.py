"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import time

from sanic import Blueprint
from api.bp.metrics.tasks import (
    second_tasks, hourly_tasks, upload_uniq_task,
)
from api.bp.metrics.compactor import compact_task
from api.bp.metrics.manager import MetricsManager

bp = Blueprint('metrics')
log = logging.getLogger(__name__)


NOT_PAGE_HIT = (
    '/api/',
    '/i/',
    '/t/',
    '/s/',
)


async def is_consenting(app, user_id: int) -> bool:
    """Return if a user consented to data processing."""
    return await app.db.fetchval("""
    SELECT consented
    FROM users
    WHERE user_id = $1
    """, user_id)


@bp.listener('before_server_start')
async def create_db(app, loop):
    """Create InfluxDB database"""
    app.metrics = MetricsManager(app, loop)

    if not app.econfig.ENABLE_METRICS:
        return

    dbname = app.econfig.METRICS_DATABASE

    log.info(f'Creating database {dbname}')
    await app.metrics.influx.create_database(db=dbname)


@bp.listener('after_server_start')
async def start_tasks(app, _loop):
    """Spawn various metric-related tasks."""
    if not app.econfig.ENABLE_METRICS:
        return

    app.sched.spawn_periodic(
        second_tasks, [app],
        1
    )

    app.sched.spawn_periodic(
        hourly_tasks, [app],
        3600
    )

    app.sched.spawn_periodic(
        upload_uniq_task, [app],
        86400
    )

    app.sched.spawn_periodic(
        compact_task, [app],
        app.econfig.METRICS_COMPACT_GENERALIZE
    )


@bp.listener('after_server_stop')
async def close_worker(app, loop):
    await app.metrics.stop()


@bp.middleware('request')
async def on_request(request):
    if not request.app.econfig.ENABLE_METRICS:
        return

    # increase the counter on every request
    request.app.rate_requests += 1

    # so we can measure response latency
    request['start_time'] = time.monotonic()

    # page hits are non-api requests
    if not any(pat in request.url for pat in NOT_PAGE_HIT):
        request.app.page_hit_counter += 1


@bp.middleware('response')
async def on_response(request, response):
    if not request.app.econfig.ENABLE_METRICS:
        return

    metrics = request.app.metrics

    # increase the counter on every response from server
    request.app.rate_response += 1

    try:
        # calculate latency to get a response, and submit that to influx
        # this field won't help in the case of network failure
        latency = time.monotonic() - request['start_time']

        # submit the metric as milliseconds since it is more tangible in
        # normal scenarios
        await metrics.submit('response_latency', latency * 1000)
    except KeyError:
        pass
