# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncpg

from sanic import Blueprint, response

from api.common import delete_file, delete_shorten
from api.schema import validate, ADMIN_MODIFY_FILE
from api.errors import BadInput
from api.decorators import admin_route

bp = Blueprint(__name__)


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
