import logging
import zipfile
import os.path

from sanic import Blueprint, response

from ..common_auth import token_check, check_admin
from ..errors import BadInput, FeatureDisabled

log = logging.getLogger(__name__)
bp = Blueprint('datadump')


async def do_dump(app, user_id: int):
    """Make a data dump for the user."""
    # insert user in current dump state

    user_name = await app.db.fetchval("""
    SELECT username
    FROM users
    WHERE user_id = $1
    """, user_id)

    row = await app.db.fetchrow("""
    SELECT MIN(file_id), MAX(file_id), COUNT(*)
    FROM files
    WHERE uploader = $1
    """, user_id)

    print(row)
    minid = row['min']
    maxid = row['max']
    total_files = row['count']

    await app.db.execute("""
    INSERT INTO current_dump_state (user_id, current_id, last_id, total_files, files_done)
    VALUES ($1, $2, $3, $4, 0)
    """, user_id, minid, maxid, total_files)

    # start iterating over files and adding them to a dump

    # first, create a dump
    # zip file?
    # yeah, zip files!
    zip_path = os.path.join(app.econfig.DUMP_FOLDER, f'{user_id}_{user_name}.zip')
    log.info(f'Path to zip: {zip_path}')

    zipdump = zipfile.ZipFile(zip_path, 'x')

    current_id = minid
    files_done = 0
    while True:
        print('working on id', current_id)
        print('file', files_done, 'out of', total_files, 'files')
        if current_id is None:
            break

        # add current file to dump
        filepath = f'./{current_id}.txt'.encode('utf-8')
        zipdump.write(filepath, 'TEST')

        files_done += 1

        # update current_dump_state
        await app.db.execute("""
        UPDATE current_dump_state
        SET current_id = $1, files_done = $2
        WHERE user_id = $3
        """, current_id, files_done, user_id)

        # fetch next id
        current_id = await app.db.fetchval("""
        SELECT file_id
        FROM files
        WHERE uploader = $1
        AND   file_id > $2
        """, user_id, current_id)

    zipdump.close()

    # TODO: add shortens

    log.info(f'Dump for user {user_id} is done')
    await app.db.execute("""
    DELETE FROM current_dump_state
    WHERE user_id = $1
    """, user_id)


async def resume_dump(app, user_id: int):
    """Resume a data dump"""
    # check the current state

    # iterate over the last one

    # dispatch to user
    pass


async def dump_worker(app):
    # fetch state, if there is, resume

    user_id = await app.db.fetchrow("""
    SELECT user_id
    FROM current_dump_state
    ORDER BY start_timestamp ASC
    """)

    if user_id:
        log.info('RESUMING')
        await resume_dump(app, user_id)

    # get from queue

    next_id = await app.db.fetchval("""
    SELECT user_id
    FROM dump_queue
    ORDER BY request_timestamp ASC
    """)

    if next_id:
        log.info('MAKING DUMP')
        # remove from the queue
        await app.db.execute("""
        DELETE FROM dump_queue
        WHERE user_id = $1
        """, next_id)
        await do_dump(app, next_id)

    log.info('dump worker stop')
    app.dump_worker = None
    

async def dump_worker_wrapper(app):
    try:
        await dump_worker(app)
    except:
        log.exception('error in dump worker task')


def start_worker(app):
    if app.dump_worker:
        return

    log.info('Starting dump worker')
    app.dump_worker = app.loop.create_task(dump_worker_wrapper(app))


@bp.listener('after_server_start')
async def start_dump_worker_ss(app, loop):
    start_worker(app)


@bp.post('/api/dump/request')
async def request_data_dump(request):
    """Request a data dump to be scheduled
    at the earliest convenience of the system."""
    if not request.app.econfig.DUMP_ENABLED:
        raise FeatureDisabled('Data dumps are disabled in this instance')

    user_id = await token_check(request)

    current_work = await request.app.db.fetchval("""
    SELECT start_timestamp
    FROM current_dump_state
    WHERE user_id = $1
    """, user_id)

    if current_work is not None:
        raise BadInput('Your data dump is currently being processed.')

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
