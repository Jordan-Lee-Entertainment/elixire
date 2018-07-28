"""
elixire - admin routes
"""
import logging
import asyncpg
from math import ceil

from sanic import Blueprint, response

from ..decorators import admin_route
from ..errors import NotFound, BadInput
from ..schema import validate, ADMIN_MODIFY_FILE, ADMIN_MODIFY_USER
from ..common import delete_file, delete_shorten
from ..common.email import fmt_email, send_user_email, activate_email_send, \
    uid_from_email, clean_etoken
from ..storage import solve_domain
from .profile import get_limits


log = logging.getLogger(__name__)
bp = Blueprint('admin')


@bp.get('/api/admin/test')
@admin_route
async def test_admin(request, admin_id):
    """Get a json payload for admin users.

    This is just a test route.
    """
    return response.json({
        'admin': True
    })


@bp.get('/api/admin/listusers/<page:int>')
@admin_route
async def list_users_handler(request, admin_id, page: int):
    """List users in the service"""
    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain,
      subdomain, email, paranoid, consented
    FROM users
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($1 * 20)
    """, page)

    def _cnv(row):
        drow = dict(row)
        drow['user_id'] = str(row['user_id'])
        return drow

    return response.json(list(map(_cnv, data)))


@bp.get('/api/admin/list_inactive/<page:int>')
@admin_route
async def inactive_users_handler(request, admin_id, page: int):
    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain, subdomain,
      email, paranoid, consented
    FROM users
    WHERE active=false
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($1 * 20)
    """, page)

    def _cnv(row):
        drow = dict(row)
        drow['user_id'] = str(row['user_id'])
        return drow

    return response.json(list(map(_cnv, data)))


@bp.get('/api/admin/users/<user_id:int>')
@admin_route
async def get_user_handler(request, admin_id, user_id: int):
    """Get a user's details in the service."""
    udata = await request.app.db.fetchrow("""
    SELECT user_id, username, active, admin, domain, subdomain,
      consented, email, paranoid
    FROM users
    WHERE user_id=$1
    """, user_id)

    if not udata:
        raise NotFound('User not found')

    dudata = dict(udata)
    dudata['user_id'] = str(dudata['user_id'])
    dudata['limits'] = await get_limits(request.app.db, user_id)

    return response.json(dudata)


async def notify_activate(app, user_id: int):
    """Inform user that they got an account."""
    log.info(f'Sending activation email to {user_id}')

    body = fmt_email(app, """This is an automated email from {inst_name}
about your account request.

Your account has been activated and you can now log in at {main_url}/login.html.

Welcome to {inst_name} family!

Send an email to {support} if any questions arise.
Do not reply to this automated email.

- {inst_name}, {main_url}
    """)

    subject = fmt_email(app, "{inst_name} - Your account is now active")
    resp, user_email = await send_user_email(app, user_id,
                                             subject,
                                             body)

    if resp.status == 200:
        log.info(f'Sent email to {user_id} {user_email}')
    else:
        log.error(f'Failed to send email to {user_id} {user_email}')


@bp.post('/api/admin/activate/<user_id:int>')
@admin_route
async def activate_user(request, admin_id, user_id: int):
    """Activate one user, given its ID."""
    result = await request.app.db.execute("""
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    await notify_activate(request.app, user_id)

    return response.json({
        'success': True,
        'result': result,
    })


@bp.post('/api/admin/activate_email/<user_id:int>')
@admin_route
async def activation_email(request, admin_id, user_id):
    """Send an email to the user so they become able
    to activate their account manually."""
    await request.app.storage.invalidate(user_id, 'active')

    resp, _email = await activate_email_send(request.app, user_id)
    return response.json({
        'success': resp.status == 200,
    })


@bp.get('/api/activate_email')
async def activate_user_from_email(request):
    """Called when a user clicks the activation URL in their email."""
    try:
        email_token = str(request.raw_args['token'])
    except (KeyError, TypeError):
        raise BadInput('No token provided')

    app = request.app
    user_id = await uid_from_email(app, email_token, 'email_activation_tokens')

    res = await request.app.db.execute("""
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')
    await clean_etoken(app, email_token, 'email_activation_tokens')
    log.info(f'Activated user id {user_id}')

    return response.json({
        'success': res == 'UPDATE 1'
    })


@bp.post('/api/admin/deactivate/<user_id:int>')
@admin_route
async def deactivate_user(request, admin_id: int, user_id: int):
    """Deactivate one user, given its ID."""
    result = await request.app.db.execute("""
    UPDATE users
    SET active = false
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    return response.json({
        'success': True,
        'result': result
    })


@bp.post('/api/admin/search/user/<page:int>')
@admin_route
async def search_user(request, user_id: int, page: int):
    """Search a user by pattern matching the username."""
    try:
        pattern = str(request.json['search_term'])
    except (KeyError, TypeError, ValueError):
        raise BadInput('Invalid search_term')

    if not pattern:
        raise BadInput('Insert a pattern.')

    pattern = f'%{pattern}%'

    rows = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, consented
    FROM users
    WHERE username LIKE $1 OR user_id::text LIKE $1
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($2 * 20)
    """, pattern, page)

    res = []

    for row in rows:
        drow = dict(row)
        drow['user_id'] = str(drow['user_id'])
        res.append(drow)

    return response.json(res)


@bp.get('/api/admin/users/search')
@admin_route
async def users_search(request, admin_id):
    """New, revamped search endpoint."""
    args = request.raw_args
    active = bool(args.get('active', True))
    query = request.raw_args.get('query')
    page = int(args.get('page', 0))
    per_page = int(args.get('per_page', 20))

    def _uname_stmt(n):
        """Generate the username query statement."""
        return f'AND username LIKE ${n} OR user_id::text LIKE ${n}' \
               if query else ''

    constraints = f"""
    active = $1
    {_uname_stmt(3)}
    """

    query = f'%{query}%'

    args = [active, page]

    if query:
        args.append(query)

    users = await request.app.db.fetch(f"""
    SELECT user_id, username, active, admin, consented
    FROM users
    WHERE {constraints}
    ORDER BY user_id ASC
    LIMIT {per_page}
    OFFSET ($2 * {per_page})
    """, *args)

    args2 = [active]

    if query:
        args2.append(query)

    total_count = await request.app.db.fetchval(f"""
    SELECT COUNT(*)
    FROM users
    WHERE active = $1 {_uname_stmt(2)}
    """, *args2)

    results = []

    for row in users:
        drow = dict(row)
        drow['user_id'] = str(drow['user_id'])
        results.append(drow)

    return response.json({
        'results': results,
        'pagination': {
            'total': ceil(total_count / per_page),
            'current': page
        }
    })


@bp.patch('/api/admin/user/<user_id:int>')
@admin_route
async def modify_user(request, admin_id, user_id):
    """Modify a user's information."""
    payload = validate(request.json, ADMIN_MODIFY_USER)

    new_admin = payload.get('admin')

    # limit is in bytes
    new_limit_upload = payload.get('upload_limit')

    # integer
    new_limit_shorten = payload.get('shorten_limit')

    updated = []

    if new_admin is not None:
        # set admin
        await request.app.db.execute("""
        UPDATE users
        SET admin = $2
        WHERE user_id = $1
        """, user_id, new_admin)

        updated.append('admin')

    if new_limit_upload is not None:
        # set new upload limit
        await request.app.db.execute("""
        UPDATE limits
        SET blimit = $1
        WHERE user_id = $2
        """, new_limit_upload, user_id)

        updated.append('upload_limit')

    if new_limit_shorten is not None:
        # set new shorten limit
        await request.app.db.execute("""
        UPDATE limits
        SET shlimit = $1
        WHERE user_id = $2
        """, new_limit_shorten, user_id)

        updated.append('shorten_limit')

    return response.json(updated)


async def generic_namefetch(table, request, shortname):
    """Generic function to fetch a file or shorten
    information based on shortname."""
    fields = 'file_id, mimetype, filename, file_size, uploader, fspath, deleted, domain' \
             if table == 'files' else \
             'shorten_id, filename, redirto, uploader, deleted, domain'

    id_field = 'file_id' if table == 'files' else 'shorten_id'

    row = await request.app.db.fetchrow(f"""
    SELECT {fields}
    FROM {table}
    WHERE filename = $1
    """, shortname)

    if not row:
        return response.json(None)

    drow = dict(row)
    drow[id_field] = str(drow[id_field])
    drow['uploader'] = str(drow['uploader'])

    return response.json(drow)


@bp.get('/api/admin/file/<shortname>')
@admin_route
async def get_file_by_name(request, admin_id, shortname):
    """Get a file's information by shortname."""
    return await generic_namefetch('files', request, shortname)


@bp.get('/api/admin/shorten/<shortname>')
@admin_route
async def get_shorten_by_name(request, admin_id, shortname):
    """Get a shorten's information by shortname."""
    return await generic_namefetch('shortens', request, shortname)


async def handle_modify(atype: str, request, thing_id):
    """Generic function to work with files OR shortens."""
    table = 'files' if atype == 'file' else 'shortens'
    field = 'file_id' if atype == 'file' else 'shorten_id'

    payload = validate(request.json, ADMIN_MODIFY_FILE)

    new_domain = payload.get('domain_id')
    new_shortname = payload.get('shortname')

    updated = []

    row = await request.app.db.fetchrow(f"""
    SELECT filename, domain
    FROM {table}
    WHERE {field} = $1
    """, thing_id)

    thing_name = row['filename']
    old_domain = row['domain']

    if new_domain is not None:
        try:
            await request.app.db.execute(f"""
            UPDATE {table}
            SET domain = $1
            WHERE {field} = $2
            """, new_domain, thing_id)
        except asyncpg.ForeignKeyViolationError:
            raise BadInput('Unknown domain ID')

        # Invalidate based on the query
        to_invalidate = f'fspath:{old_domain}:{thing_name}' \
                        if atype == 'file' else \
                        f'redir:{old_domain}:{thing_name}'

        await request.app.storage.raw_invalidate(to_invalidate)
        updated.append('domain')

    if new_shortname is not None:
        # Ignores deleted files, just sets the new filename
        try:
            await request.app.db.execute(f"""
            UPDATE {table}
            SET filename = $1
            WHERE {field} = $2
            """, new_shortname, thing_id)
        except asyncpg.UniqueViolationError:
            raise BadInput('Shortname already exists.')

        # Invalidate both old and new
        await request.app.storage.raw_invalidate(*[
            f'fspath:{old_domain}:{thing_name}',
            f'fspath:{old_domain}:{new_shortname}',
        ])

        updated.append('shortname')

    return response.json(updated)


@bp.patch('/api/admin/file/<file_id:int>')
@admin_route
async def modify_file(request, admin_id, file_id):
    """Modify file information."""
    return await handle_modify('file', request, file_id)


@bp.patch('/api/admin/shorten/<shorten_id:int>')
@admin_route
async def modify_shorten(request, admin_id, shorten_id):
    """Modify file information."""
    return await handle_modify('shorten', request, shorten_id)


@bp.delete('/api/admin/file/<file_id:int>')
@admin_route
async def delete_file_handler(request, admin_id, file_id):
    """Delete a file."""
    row = await request.app.db.fetchrow("""
    SELECT filename, uploader
    FROM files
    WHERE file_id = $1
    """, file_id)

    await delete_file(request.app, row['filename'], row['uploader'])

    return response.json({
        'shortname': row['filename'],
        'uploader': str(row['uploader']),
        'success': True,
    })


@bp.delete('/api/admin/shorten/<shorten_id:int>')
@admin_route
async def delete_shorten_handler(request, admin_id, shorten_id: int):
    """Delete a shorten."""
    row = await request.app.db.fetchrow("""
    SELECT filename, uploader
    FROM shortens
    WHERE shorten_id = $1
    """, shorten_id)

    await delete_shorten(request.app, row['filename'], row['uploader'])

    return response.json({
        'shortname': row['filename'],
        'uploader': str(row['uploader']),
        'success': True,
    })


@bp.put('/api/admin/domains')
@admin_route
async def add_domain(request, admin_id: int):
    """Add a domain."""
    domain_name = str(request.json['domain'])
    is_adminonly = bool(request.json['admin_only'])
    is_official = bool(request.json['official'])

    result = await request.app.db.execute("""
    INSERT INTO domains
    (domain, admin_only, official)
    VALUES ($1, $2, $3)
    """, domain_name, is_adminonly, is_official)

    keys = solve_domain(domain_name)
    await request.app.storage.raw_invalidate(*keys)

    return response.json({
        'success': True,
        'result': result
    })


@bp.delete('/api/admin/domains/<domain_id:int>')
@admin_route
async def remove_domain(request, admin_id: int, domain_id: int):
    """Remove a domain."""
    domain_name = await request.app.db.fetchval("""
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    files_count = await request.app.db.execute("""
    UPDATE files set domain = 0 WHERE domain = $1
    """, domain_id)

    shorten_count = await request.app.db.execute("""
    UPDATE shortens set domain = 0 WHERE domain = $1
    """, domain_id)

    users_count = await request.app.db.execute("""
    UPDATE users set domain = 0 WHERE domain = $1
    """, domain_id)

    users_shorten_count = await request.app.db.execute("""
    UPDATE users set shorten_domain = 0 WHERE shorten_domain = $1
    """, domain_id)

    result = await request.app.db.execute("""
    DELETE FROM domains
    WHERE domain_id = $1
    """, domain_id)

    keys = solve_domain(domain_name)
    await request.app.storage.raw_invalidate(*keys)

    return response.json({
        'success': True,
        'file_move_result': files_count,
        'shorten_move_result': shorten_count,
        'users_move_result': users_count,
        'users_shorten_move_result': users_shorten_count,
        'result': result
    })


@bp.get('/api/admin/domains/<domain_id:int>')
@admin_route
async def get_domain_stats(request, admin_id, domain_id):
    """Get information about a domain."""
    raw_info = await request.app.db.fetchrow("""
    SELECT domain, official, admin_only, cf_enabled
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    dinfo = dict(raw_info)

    stats = {}

    stats['users'] = await request.app.db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE domain = $1
    """, domain_id)

    stats['files'] = await request.app.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE domain = $1
    """, domain_id)

    stats['shortens'] = await request.app.db.fetchval("""
    SELECT COUNT(*)
    FROM shortens
    WHERE domain = $1
    """, domain_id)

    public_stats = {}

    public_stats['users'] = await request.app.db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE domain = $1 AND consented = true
    """, domain_id)

    public_stats['files'] = await request.app.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    JOIN users
      ON users.user_id = files.uploader
    WHERE files.domain = $1 AND users.consented = true
    """, domain_id)

    public_stats['shortens'] = await request.app.db.fetchval("""
    SELECT COUNT(*)
    FROM shortens
    JOIN users
      ON users.user_id = shortens.uploader
    WHERE shortens.domain = $1 AND users.consented = true
    """, domain_id)

    return response.json({
        'info': dinfo,
        'stats': stats,
        'public_stats': public_stats,
    })
