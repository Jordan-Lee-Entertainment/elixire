import logging
import time

from sanic import Blueprint
from .tasks import second_tasks, hourly_tasks, upload_uniq_task
from .manager import MetricsManager

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
    app.metrics = MetricsManager(app, loop)

    if not app.econfig.ENABLE_METRICS:
        return

    dbname = app.econfig.METRICS_DATABASE

    log.info(f'Creating database {dbname}')
    await app.metrics.influx.create_database(db=dbname)


@bp.listener('after_server_start')
async def start_tasks(app, loop):
    # spawn tasks
    app._sec_tasks = loop.create_task(second_tasks(app))
    app._hour_tasks = loop.create_task(hourly_tasks(app))
    app._uniq_task = loop.create_task(upload_uniq_task(app))


@bp.listener('before_server_stop')
async def close_metrics(app, loop):
    app._sec_tasks.cancel()
    app._hour_tasks.cancel()
    app._uniq_task.cancel()


@bp.listener('after_server_stop')
async def close_worker(app, loop):
    metrics = app.metrics
    metrics._worker.cancel()
    await metrics.finish_all()


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
