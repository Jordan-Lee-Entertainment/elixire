import os.path
import logging

from sanic import Blueprint, response
from api.errors import BadInput, FeatureDisabled
from api.common.auth import token_check, check_admin
from .tasks import start_janitor, start_worker

log = logging.getLogger(__name__)
bp = Blueprint(__name__)


@bp.listener('after_server_start')
async def start_dump_worker_ss(app, _loop):
    """Start the dump worker on application startup
    so we can resume if any is there to resume."""
    if app.econfig.DUMP_ENABLED:
        start_worker(app)
        start_janitor(app)
    else:
        log.info('data dumps are disabled!')


@bp.post('/api/dump/request')
async def request_data_dump(request):
    """Request a data dump to be scheduled
    at the earliest convenience of the system.

    This works by having two states:
     - a dump queue
     - the dump state

    Every user adds themselves to the dump queue with this route.
    Only one user can be in the dump state at a time.

    The dump worker queries the dump state at least once to know
    when to resume a dump (in the case of application failure in the middle of a dump),
    If any user is in there, it resumes the dump, check resume_dump().

    After that, it checks the oldest person in the queue, if there is any,
    it starts making the dump for that person, check do_dump().

    After resume_dump or do_dump finish they call dispatch_dump() which sends
    an email to the user containing the dump.
    """
    if not request.app.econfig.DUMP_ENABLED:
        raise FeatureDisabled('Data dumps are disabled in this instance')

    user_id = await token_check(request)

    # check if user is already underway
    current_work = await request.app.db.fetchval("""
    SELECT start_timestamp
    FROM current_dump_state
    WHERE user_id = $1
    """, user_id)

    if current_work is not None:
        raise BadInput('Your data dump is currently being processed.')

    # so that intellectual users don't queue themselves twice.
    in_queue = await request.app.db.fetchval("""
    SELECT request_timestamp
    FROM dump_queue
    WHERE user_id = $1
    """, user_id)

    if in_queue:
        raise BadInput('You already requested your data dump.')

    # insert into queue
    await request.app.db.execute("""
    INSERT INTO dump_queue (user_id)
    VALUES ($1)
    """, user_id)

    start_worker(request.app)

    return response.json({
        'success': True,
    })


@bp.get('/api/dump/status')
async def data_dump_user_status(request):
    """Give information about the current dump for the user,
    if one exists."""
    user_id = await token_check(request)

    row = await request.app.db.fetchrow("""
    SELECT user_id, start_timestamp, current_id, total_files, files_done
    FROM current_dump_state
    WHERE user_id = $1
    """, user_id)

    if not row:
        queue = await request.app.db.fetch("""
        SELECT user_id
        FROM dump_queue
        ORDER BY request_timestamp ASC
        """)

        queue = [r['user_id'] for r in queue]

        try:
            pos = queue.index(user_id)
            return response.json({
                'state': 'in_queue',
                'position': pos + 1,
            })
        except ValueError:
            return response.json({
                'state': 'not_in_queue'
            })

    return response.json({
        'state': 'processing',
        'start_timestamp': row['start_timestamp'].isoformat(),
        'current_id': str(row['current_id']),
        'total_files': row['total_files'],
        'files_done': row['files_done']
    })


@bp.get('/api/admin/dump_status')
async def data_dump_global_status(request):
    """Only for admins: all stuff related to data dump state."""
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    queue = await request.app.db.fetch("""
    SELECT user_id
    FROM dump_queue
    ORDER BY request_timestamp ASC
    """)

    queue = [str(el['user_id']) for el in queue]

    current = await request.app.db.fetchrow("""
    SELECT user_id, total_files, files_done
    FROM current_dump_state
    """)

    return response.json({
        'queue': queue,
        'current': dict(current or {})
    })


@bp.get('/api/dump_get')
async def get_dump(request):
    """Download the dump file."""
    try:
        dump_token = str(request.args['key'][0])
    except (KeyError, TypeError, ValueError):
        raise BadInput('No valid key provided.')

    user_id = await request.app.db.fetchval("""
    SELECT user_id
    FROM email_dump_tokens
    WHERE hash = $1 AND now() < expiral
    """, dump_token)

    if not user_id:
        raise BadInput('Invalid or expired token.')

    user_name = await request.app.db.fetchval("""
    SELECT username
    FROM users
    WHERE user_id = $1
    """, user_id)

    zip_path = os.path.join(
        request.app.econfig.DUMP_FOLDER,
        f'{user_id}_{user_name}.zip',
    )

    return await response.file_stream(zip_path)
