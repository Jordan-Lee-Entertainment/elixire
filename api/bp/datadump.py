"""
elixire - datadump API
"""

import json
import time
import logging
import asyncio
import zipfile
import pathlib
import os.path

from sanic import Blueprint, response

from ..common.auth import token_check, check_admin
from ..common.email import gen_email_token, send_email
from ..errors import BadInput, FeatureDisabled

log = logging.getLogger(__name__)
bp = Blueprint('datadump')


def _dump_json(zipdump, filepath, obj):
    objstr = json.dumps(obj, indent=4)
    zipdump.writestr(filepath, objstr)


async def open_zipdump(app, user_id, resume=False) -> zipfile.ZipFile:
    """Open the zip file relating to your dump."""
    user_name = await app.db.fetchval("""
    SELECT username
    FROM users
    WHERE user_id = $1
    """, user_id)

    zip_path = os.path.join(
        app.econfig.DUMP_FOLDER,
        f'{user_id}_{user_name}.zip',
    )

    if not resume:
        # we use w instead of x because
        # if the dump already exists we should
        # just overwrite it.
        return zipfile.ZipFile(zip_path, 'w',
                               compression=zipfile.ZIP_DEFLATED), user_name

    return zipfile.ZipFile(zip_path, 'a',
                           compression=zipfile.ZIP_DEFLATED), user_name


async def dump_user_data(app, zipdump, user_id):
    """Insert user information into the dump."""
    udata = await app.db.fetchrow("""
    SELECT user_id, username, active, password_hash, email,
           consented, admin, subdomain, domain
    FROM users
    WHERE user_id = $1
    """, user_id)

    _dump_json(zipdump, 'user_data.json', dict(udata))


async def dump_user_bans(app, zipdump, user_id):
    """Insert user bans, if any, into the dump."""
    bans = await app.db.fetch("""
    SELECT user_id, reason, end_timestamp
    FROM bans
    WHERE user_id = $1
    """, user_id)

    treated = []
    for row in bans:
        goodrow = {
            'user_id': row['user_id'],
            'reason': row['reason'],
            'end_timestamp': row['end_timestamp'].isoformat(),
        }

        treated.append(goodrow)

    _dump_json(zipdump, 'bans.json', treated)


async def dump_user_limits(app, zipdump, user_id: int):
    """Write the current limits for the user in the dump."""
    limits = await app.db.fetchrow("""
    SELECT user_id, blimit, shlimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    _dump_json(zipdump, 'limits.json', dict(limits))


async def dump_user_files(app, zipdump, user_id):
    """Dump all information about the user's files."""
    all_files = await app.db.fetch("""
    SELECT file_id, mimetype, filename, file_size, uploader, domain
    FROM files
    WHERE uploader = $1
    """, user_id)

    all_files_l = []
    for row in all_files:
        all_files_l.append(dict(row))

    _dump_json(zipdump, 'files.json', all_files_l)


async def dump_user_shortens(app, zipdump, user_id):
    """Dump all information about the user's shortens."""
    all_shortens = await app.db.fetch("""
    SELECT shorten_id, filename, redirto, domain
    FROM shortens
    WHERE uploader = $1
    """, user_id)

    all_shortens_l = []
    for row in all_shortens:
        all_shortens_l.append(dict(row))

    _dump_json(zipdump, 'shortens.json', all_shortens_l)


async def dump_files(app, zipdump, user_id, minid, files_done):
    """Dump files into the data dump zip."""

    # start from minimum id
    current_id = minid

    while True:
        if files_done % 100 == 0:
            log.info(f'Worked {files_done} files for user {user_id}')

        if current_id is None:
            log.info(f'Finished file takeout for {user_id}')
            break

        # add current file to dump
        fdata = await app.db.fetchrow("""
        SELECT fspath, filename
        FROM files
        WHERE file_id = $1
        """, current_id)

        fspath = fdata['fspath']
        filename = fdata['filename']
        ext = os.path.splitext(fspath)[-1]

        filepath = f'./files/{current_id}_{filename}{ext}'
        try:
            fut = app.loop.run_in_executor(None,
                                           zipdump.write,
                                           fspath, filepath)

            await fut
        except FileNotFoundError:
            log.warning(f'File not found: {current_id} {filename}')

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

        ORDER BY file_id ASC
        LIMIT 1
        """, user_id, current_id)


async def dispatch_dump(app, user_id: int, user_name: str):
    """Dispatch the data dump to a user."""
    log.info(f'Dispatching dump for {user_id} {user_name!r}')

    _inst_name = app.econfig.INSTANCE_NAME
    _support = app.econfig.SUPPORT_EMAIL

    dump_token = await gen_email_token(app, user_id, 'email_dump_tokens')

    await app.db.execute("""
    INSERT INTO email_dump_tokens (hash, user_id)
    VALUES ($1, $2)
    """, dump_token, user_id)

    email_body = f"""This is an automated email from {_inst_name}
about your data dump.

Visit {app.econfig.MAIN_URL}/api/dump_get?token={dump_token} to fetch your
data dump.

The URL will be invalid in 6 hours.
Do not share this URL. Nobody will ask you for this URL.

Send an email to {_support} if any questions arise.
Do not reply to this automated email.

- {_inst_name}, {app.econfig.MAIN_URL}
    """

    user_email = await app.db.fetchval("""
    SELECT email
    FROM users
    WHERE user_id = $1
    """, user_id)

    resp = await send_email(app, user_email,
                            f'{_inst_name} - Your data dump is here!',
                            email_body)

    if resp.status == 200:
        log.info(f'Sent email to {user_id} {user_email}')

        # remove from current state
        await app.db.execute("""
        DELETE FROM current_dump_state
        WHERE user_id = $1
        """, user_id)
    else:
        log.error(f'Failed to send email to {user_id} {user_email}')


async def dump_static(app, zipdump, user_id):
    """Dump static files. Those files are JSON encoded
    with the required information."""
    await dump_user_data(app, zipdump, user_id)
    await dump_user_bans(app, zipdump, user_id)
    await dump_user_limits(app, zipdump, user_id)
    await dump_user_files(app, zipdump, user_id)
    await dump_user_shortens(app, zipdump, user_id)


async def do_dump(app, user_id: int):
    """Make a data dump for the user."""
    # insert user in current dump state
    row = await app.db.fetchrow("""
    SELECT MIN(file_id), COUNT(*)
    FROM files
    WHERE uploader = $1
    """, user_id)

    minid = row['min']
    total_files = row['count']

    log.info(f'==TAKEOUT==\n'
             f'uid {user_id}\n'
             f'min file id {minid}\n'
             f'total files {total_files}')

    await app.db.execute("""
    INSERT INTO current_dump_state
        (user_id, current_id, total_files, files_done)
    VALUES
        ($1, $2, $3, 0)
    """, user_id, minid, total_files)

    zipdump, user_name = await open_zipdump(app, user_id)

    try:
        # those dumps just get stuff from DB
        # and write them into JSON files insize the zip
        await dump_static(app, zipdump, user_id)

        # this is the longest operation for a dump
        # and because of that, it is resumable, so in the case
        # of an application failure, the system should be able to
        # know where it left off and continue writing to the zip file.
        await dump_files(app, zipdump, user_id, minid, 0)

        # Finally, dispatch the ZIP file via email to the user.
        await dispatch_dump(app, user_id, user_name)
    except Exception:
        log.exception('Error on dumping')
    finally:
        zipdump.close()


async def resume_dump(app, user_id: int):
    """Resume a data dump"""
    # check the current state
    row = await app.db.fetchrow("""
    SELECT current_id, files_done
    FROM current_dump_state
    WHERE user_id = $1
    """, user_id)

    log.info(f'Resuming for {user_id} files_done: {row["files_done"]}')

    zipdump, user_name = await open_zipdump(app, user_id, True)

    try:
        # Redump static files.
        await dump_static(app, zipdump, user_id)

        await dump_files(app, zipdump, user_id, row['current_id'],
                         row['files_done'])

        await dispatch_dump(app, user_id, user_name)
    except Exception:
        log.exception('error on dump files resume')
    finally:
        zipdump.close()



async def dump_worker(app):
    """Main dump worker.

    Works dump resuming, manages the next user on the queue, etc.
    """
    log.info('dump worker start')

    # fetch state, if there is, resume
    user_id = await app.db.fetchval("""
    SELECT user_id
    FROM current_dump_state
    ORDER BY start_timestamp ASC
    """)

    if user_id:
        await resume_dump(app, user_id)

    # get from queue
    next_id = await app.db.fetchval("""
    SELECT user_id
    FROM dump_queue
    ORDER BY request_timestamp ASC
    """)

    if next_id:
        # remove from the queue
        await app.db.execute("""
        DELETE FROM dump_queue
        WHERE user_id = $1
        """, next_id)

        await do_dump(app, next_id)

        # use recursion so that
        # in the next call, we will fetch
        # the next user in the queue

        # if no user is in the queue, the function
        # will stop.
        return await dump_worker(app)

    log.info('dump worker stop')
    app.dump_worker = None


async def dump_worker_wrapper(app):
    """Wrap the dump_worker inside a try/except block for logging."""
    try:
        await dump_worker(app)
    except Exception:
        log.exception('error in dump worker task')


def start_worker(app):
    """Start the dump worker, but not start more than 1 of them."""
    if app.dump_worker:
        return

    log.info('Starting dump worker')
    app.dump_worker = app.loop.create_task(dump_worker_wrapper(app))


async def dump_janitor(app):
    """Main data dump janitor task.

    This checks the dump folder every DUMP_JANITOR_PERIOD amount
    of seconds.

    If there is a file that is more than 6 hours old, it gets deleted.
    """
    dumps = pathlib.Path(app.econfig.DUMP_FOLDER)
    while True:
        # iterate over all ((ZIP)) files inside the dump folder
        for fpath in dumps.glob('*.zip'):
            fstat = fpath.stat()
            now = time.time()

            # if the current time - the last time of modification
            # is more than 6 hours, we delete.
            file_life = now - fstat.st_mtime
            if file_life > 21600:
                log.info(f'janitor: cleaning {fpath} since it is more than 6h '
                         f'(life: {file_life}s)')
                fpath.unlink()
            else:
                log.info(f'Ignoring {fpath}, life {file_life}s < 21600')

        await asyncio.sleep(app.econfig.DUMP_JANITOR_PERIOD)


async def dump_janitor_wrapper(app):
    """Spawn a janitor task inside a try/except."""
    try:
        await dump_janitor(app)
    except Exception:
        log.exception('error in dump janitor task')


def start_janitor(app):
    """Start dump janitor."""
    app.janitor_task = app.loop.create_task(dump_janitor(app))


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
        dump_token = str(request.args['token'][0])
    except (KeyError, TypeError, ValueError):
        raise BadInput('No valid token provided.')

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
