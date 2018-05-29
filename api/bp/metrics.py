import logging
import asyncio

from sanic import Blueprint


log = logging.getLogger(__name__)
bp = Blueprint('metrics')


def point(measure, value):
    return {
        'measurement': measure,
        'fields': {'value': value},
    }


async def ratetask(app):
    try:
        while True:
            r = await app.ifxdb.ping()
            log.info('r: %s', r)

            # submit and reset what we have
            # every second
            await app.ifxdb.write(point('request', app.rate_requests))
            app.rate_requests = 0

            await app.ifxdb.write(point('response', app.rate_response))
            app.rate_response = 0

            await asyncio.sleep(1)
    except Exception:
        log.exception('ratetask err')


@bp.listener('after_server_start')
async def create_db(app, loop):
    if app.econfig.ENABLE_METRICS:
        dbname = app.econfig.METRICS_DATABASE

        log.info(f'Creating database {dbname}')
        await app.ifxdb.create_database(db=dbname)
        app.ratetask = loop.create_task(ratetask(app))


@bp.middleware('request')
async def on_request(request):
    if not request.app.econfig.ENABLE_METRICS:
        return

    # increase the counter on every request
    request.app.rate_requests += 1


@bp.middleware('response')
async def on_response(request, response):
    if not request.app.econfig.ENABLE_METRICS:
        return

    # increase the counter on every response from server
    request.app.rate_response += 1
