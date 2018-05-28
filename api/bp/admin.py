"""
elixire - admin routes
"""
import logging
import asyncpg

from sanic import Blueprint, response

from ..common_auth import token_check, check_admin
from ..errors import NotFound, BadInput
from ..decorators import admin_route
from ..schema import validate, ADMIN_MODIFY_FILE


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
    SELECT user_id, username, active, admin, domain, subdomain, email, paranoid
    FROM users
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
    SELECT user_id, username, active, admin, domain, subdomain, email, paranoid
    FROM users
    WHERE active=false
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
    SELECT user_id, username, active, admin, domain, subdomain, consented, email, paranoid
    FROM users
    WHERE user_id=$1
    """, user_id)

    if not udata:
        raise NotFound('User not found')

    dudata = dict(udata)
    dudata['user_id'] = str(dudata['user_id'])

    return response.json(dudata)


@bp.post('/api/admin/activate/<user_id:int>')
@admin_route
async def activate_user(request, admin_id, user_id: int):
    """Activate one user, given its ID."""
    caller_id = await token_check(request)
    await check_admin(request, caller_id, True)

    result = await request.app.db.execute("""
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    return response.json({
        'success': True,
        'result': result,
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


async def generic_namefetch(table, request, shortname):
    """Generic function to fetch a file or shorten information based on shortname."""
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
        return

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
        await request.app.storage.raw_invalidate(f'fspath:{old_domain}:{thing_name}')
        await request.app.storage.raw_invalidate(f'fspath:{old_domain}:{new_shortname}')

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
    FROM files
    WHERE domain = $1
    """, domain_id)

    return response.json({
        'info': dinfo,
        'stats': stats,
    })
