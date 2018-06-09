import logging
import asyncio
import time

from sanic import Blueprint


log = logging.getLogger(__name__)
bp = Blueprint('metrics')
NOT_PAGE_HIT = (
    '/api/',
    '/i/',
    '/t/',
    '/s/',
)


def point(measure, value):
    return {
        'measurement': measure,
        'fields': {'value': value},
    }


async def submit(app, title, value, task=False):
    """Submit a datapoint to InfluxDB.
    
    This was written so that the datapoint write routine
    could be spawned in a task, decreasing overall response latency
    after it is measured.
    """
    if not app.econfig.ENABLE_METRICS:
        return

    datapoint = point(title, value)

    if task:
        app.loop.create_task(app.ifxdb.write(datapoint))
    else:
        try:
            await app.ifxdb.write(datapoint)
        except Exception:
            log.exception('Failed to submit datapoint')


async def ratetask(app):
    try:
        while True:
            # submit and reset what we have
            # every second
            await submit(app, 'request', app.rate_requests)
            app.rate_requests = 0

            await submit(app, 'response', app.rate_response)
            app.rate_response = 0

            await asyncio.sleep(1)
    except Exception:
        log.exception('ratetask err')


async def file_upload_task(app):
    try:
        while True:
            await submit(app, 'file_upload_hour', app.file_upload_counter)
            app.file_upload_counter = 0
            await asyncio.sleep(3600)
    except Exception:
        log.exception('file upload task err')


async def page_hit_task(app):
    try:
        while True:
            await submit(app, 'page_hit', app.page_hit_counter)
            app.page_hit_counter = 0
            await asyncio.sleep(1)
    except Exception:
        log.exception('file upload task err')


async def file_count_task(app):
    try:
        while True:
            total_files = await app.db.fetchval("""
            SELECT COUNT(*)
            FROM files
            """)
            await submit(app, 'total_files', total_files)
            await asyncio.sleep(3600)
    except Exception:
        log.exception('file count task err')


@bp.listener('after_server_start')
async def create_db(app, loop):
    if not app.econfig.ENABLE_METRICS:
        return

    dbname = app.econfig.METRICS_DATABASE

    log.info(f'Creating database {dbname}')
    await app.ifxdb.create_database(db=dbname)

    # spawn tasks
    app.ratetask = loop.create_task(ratetask(app))
    app.file_upload_task = loop.create_task(file_upload_task(app))
    app.page_hit_task = loop.create_task(page_hit_task(app))
    app.file_count_task = app.loop.create_task(file_count_task(app))


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

    # increase the counter on every response from server
    request.app.rate_response += 1

    # calculate latency to get a response, and submit that to influx
    # this field won't help in the case of network failure
    latency = time.monotonic() - request['start_time']

    # submit the metric as milliseconds since it is more tangible in
    # normal scenarios
    await submit(request.app, 'response_latency', latency * 1000, True)
