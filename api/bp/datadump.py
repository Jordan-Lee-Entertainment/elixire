import logging

from sanic import Blueprint, response

from ..common_auth import token_check, check_admin
from ..errors import BadInput

log = logging.getLogger(__name__)
bp = Blueprint('datadump')


async def dump_worker(app):
    log.info('dump worker start')


@bp.listener('after_server_start')
async def start_dump_worker_ss(app, loop):
    loop.create_task(dump_worker(app))


@bp.post('/api/dump/request')
async def request_data_dump(request):
    """Request a data dump to be scheduled
    at the earliest convenience of the system."""
    pass


@bp.get('/api/dump/status')
async def data_dump_user_status(request):
    """Give information about the current dump for the user,
    if one exists."""
    user_id = await token_check(request)

    row = await request.app.db.fetchrow("""
    SELECT user_id, start_timestamp, current_id, last_id, total_files, files_done
    FROM current_dump_state
    WHERE user_id = $1
    """, user_id)

    if not row:
        # TODO: show current state in queue, if any
        raise BadInput('Your dump is not being processed right now.')

    return response.json({
        'start_timestamp': row['start_timestamp'].isotimestamp(),
        'current_id': row['current_id'],
        'last_id': row['last_id'],
        'total_files': row['total_files'],
        'files_done': row['files_done']
    })


@bp.get('/api/dump/global_status')
async def data_dump_global_status(request):
    """Only for admins: all stuff related to data dump state."""
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    queue = await request.app.db.fetch("""
    SELECT user_id FROM dump_queue
    """)

    queue = [el['user_id'] for el in queue]

    current = await request.app.db.fetchrow("""
    SELECT user_id, total_files, files_done
    FROM current_dump_state
    """)

    return response.json({
        'queue': queue,
        'current': dict(current or {})
    })
