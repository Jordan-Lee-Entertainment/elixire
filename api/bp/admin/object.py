# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncpg

from sanic import Blueprint, response

from api.common import delete_file, delete_shorten
from api.schema import validate, ADMIN_MODIFY_FILE
from api.errors import BadInput
from api.decorators import admin_route

from api.bp.admin.audit_log_actions.object import (
    ObjectEditAction, ObjectDeleteAction
)

from api.common.fetch import (
    OBJ_MAPPING
)

bp = Blueprint(__name__)


async def _handler_object(request, obj_type: str,
                          obj_fname: str) -> response:
    """Handler for fetching files/shortens."""
    id_handler, obj_handler = OBJ_MAPPING[obj_type]

    conn = request.app.db

    obj_id = await id_handler(conn, obj_fname)

    if obj_id is None:
        raise BadInput('Object not found')

    return response.json(
        await obj_handler(conn, obj_id)
    )


@bp.get('/api/admin/file/<shortname>')
@admin_route
async def get_file_by_name(request, _admin_id, shortname):
    """Get a file's information by shortname."""
    return await _handler_object(request, 'file', shortname)


@bp.get('/api/admin/shorten/<shortname>')
@admin_route
async def get_shorten_by_name(request, _admin_id, shortname):
    """Get a shorten's information by shortname."""
    return await _handler_object(request, 'shorten', shortname)


async def handle_modify(obj_type: str, request,
                        obj_id: int) -> response:
    """Generic function to work with files OR shortens."""
    table = 'files' if obj_type == 'file' else 'shortens'
    field = 'file_id' if obj_type == 'file' else 'shorten_id'

    payload = validate(request.json, ADMIN_MODIFY_FILE)

    new_domain = payload.get('domain_id')
    new_shortname = payload.get('shortname')

    updated = []

    row = await request.app.db.fetchrow(f"""
    SELECT filename, domain
    FROM {table}
    WHERE {field} = $1
    """, obj_id)

    obj_name = row['filename']
    old_domain = row['domain']

    if new_domain is not None:
        try:
            await request.app.db.execute(f"""
            UPDATE {table}
            SET domain = $1
            WHERE {field} = $2
            """, new_domain, obj_id)
        except asyncpg.ForeignKeyViolationError:
            raise BadInput('Unknown domain ID')

        # Invalidate based on the query
        to_invalidate = 'fspath' if obj_type == 'file' else 'redir'
        to_invalidate = f'{to_invalidate}:{old_domain}:{obj_name}'

        await request.app.storage.raw_invalidate(to_invalidate)
        updated.append('domain')

    if new_shortname is not None:
        # Ignores deleted files, just sets the new filename
        try:
            await request.app.db.execute(f"""
            UPDATE {table}
            SET filename = $1
            WHERE {field} = $2
            """, new_shortname, obj_id)
        except asyncpg.UniqueViolationError:
            raise BadInput('Shortname already exists.')

        # Invalidate both old and new
        await request.app.storage.raw_invalidate(*[
            f'fspath:{old_domain}:{obj_name}',
            f'fspath:{old_domain}:{new_shortname}',
        ])

        updated.append('shortname')

    return response.json(updated)


@bp.patch('/api/admin/file/<file_id:int>')
@admin_route
async def modify_file(request, _admin_id, file_id):
    """Modify file information."""

    async with ObjectEditAction(request, file_id, 'file'):
        return await handle_modify('file', request, file_id)


@bp.patch('/api/admin/shorten/<shorten_id:int>')
@admin_route
async def modify_shorten(request, _admin_id, shorten_id):
    """Modify file information."""

    async with ObjectEditAction(request, shorten_id, 'shorten'):
        return await handle_modify('shorten', request, shorten_id)


@bp.delete('/api/admin/file/<file_id:int>')
@admin_route
async def delete_file_handler(request, _admin_id, file_id):
    """Delete a file."""
    row = await request.app.db.fetchrow("""
    SELECT filename, uploader
    FROM files
    WHERE file_id = $1
    """, file_id)

    if row is None:
        raise BadInput('File not found')

    async with ObjectDeleteAction(request, file_id, 'file'):
        await delete_file(request.app, row['filename'], row['uploader'])

    return response.json({
        'shortname': row['filename'],
        'uploader': str(row['uploader']),
        'success': True,
    })


@bp.delete('/api/admin/shorten/<shorten_id:int>')
@admin_route
async def delete_shorten_handler(request, _admin_id, shorten_id: int):
    """Delete a shorten."""
    row = await request.app.db.fetchrow("""
    SELECT filename, uploader
    FROM shortens
    WHERE shorten_id = $1
    """, shorten_id)

    if row is None:
        raise BadInput('Shorten not found')

    async with ObjectDeleteAction(request, shorten_id, 'shorten'):
        await delete_shorten(request.app,
                             row['filename'],
                             row['uploader'])

    return response.json({
        'shortname': row['filename'],
        'uploader': str(row['uploader']),
        'success': True,
    })
