# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from sanic import Blueprint, response

from api.schema import validate, ADMIN_MODIFY_DOMAIN, ADMIN_SEND_DOMAIN_EMAIL
from api.decorators import admin_route
from api.common.email import send_user_email
from api.storage import solve_domain
from api.errors import BadInput

from api.bp.admin.audit_log_actions.domain import (
    DomainAddCtx, DomainEditCtx, DomainRemoveCtx
)

from api.common.domain import get_domain_info

bp = Blueprint(__name__)


@bp.put('/api/admin/domains')
@admin_route
async def add_domain(request, admin_id: int):
    """Add a domain."""
    domain_name = str(request.json['domain'])
    is_adminonly = bool(request.json['admin_only'])
    is_official = bool(request.json['official'])

    # default 3
    permissions = int(request.json.get('permissions', 3))

    db = request.app.db

    result = await db.execute("""
    INSERT INTO domains
        (domain, admin_only, official, permissions)
    VALUES
        ($1, $2, $3, $4)
    """, domain_name, is_adminonly, is_official, permissions)

    domain_id = await db.fetchval("""
    SELECT domain_id
    FROM domains
    WHERE domain = $1
    """, domain_name)

    async with DomainAddCtx(request) as ctx:
        ctx.insert(domain_id=domain_id)

        if 'owner_id' in request.json:
            owner_id = int(request.json['owner_id'])
            ctx.insert(owner_id=owner_id)

            await db.execute("""
            INSERT INTO domain_owners (domain_id, user_id)
            VALUES ($1, $2)
            """, domain_id, int(request.json['owner_id']))

    keys = solve_domain(domain_name)
    await request.app.storage.raw_invalidate(*keys)

    return response.json({
        'success': True,
        'result': result,
        'new_id': domain_id,
    })


async def _dp_check(db, domain_id: int, payload: dict,
                    updated_fields: list, field: str):
    """Check a field inside the payload and update it if it exists."""

    if field in payload:
        await db.execute(f"""
        UPDATE domains
        SET {field} = $1
        WHERE domain_id = $2
        """, payload[field], domain_id)

        updated_fields.append(field)


@bp.patch('/api/admin/domains/<domain_id:int>')
@admin_route
async def patch_domain(request, admin_id: int, domain_id: int):
    """Patch a domain's information"""
    payload = validate(request.json, ADMIN_MODIFY_DOMAIN)

    updated_fields = []
    db = request.app.db

    async with DomainEditCtx(request, domain_id):
        if 'owner_id' in payload:
            exec_out = await db.execute("""
            UPDATE domain_owners
            SET user_id = $1
            WHERE domain_id = $2
            """, int(payload['owner_id']), domain_id)

            if exec_out != 'UPDATE 0':
                updated_fields.append('owner_id')

        # since we're passing updated_fields which is a reference to the
        # list, it can be mutaded and it will propagate into this function.
        await _dp_check(db, domain_id, payload, updated_fields, 'admin_only')
        await _dp_check(db, domain_id, payload, updated_fields, 'official')
        await _dp_check(db, domain_id, payload, updated_fields, 'permissions')

    return response.json({
        'updated': updated_fields,
    })


@bp.post('/api/admin/email_domain/<domain_id:int>')
@admin_route
async def email_domain(request, admin_id: int, domain_id: int):
    payload = validate(request.json, ADMIN_SEND_DOMAIN_EMAIL)

    owner_id = await request.app.db.fetchval("""
    SELECT user_id
    FROM domain_owners
    WHERE domain_id = $1
    """, domain_id)

    resp, user_email = await send_user_email(
        request.app, owner_id, payload['subject'], payload['body'])

    return response.json({
        'success': resp.status == 200,
        'owner_id': owner_id,
        'owner_email': user_email,
    })


@bp.put('/api/admin/domains/<domain_id:int>/owner')
@admin_route
async def add_owner(request, admin_id: int, domain_id: int):
    """Add an owner to a single domain."""
    try:
        owner_id = int(request.json['owner_id'])
    except (ValueError, KeyError):
        raise BadInput('Invalid number for owner ID')

    async with DomainEditCtx(request, domain_id):
        exec_out = await request.app.db.execute("""
        INSERT INTO domain_owners (domain_id, user_id)
        VALUES ($1, $2)
        """, domain_id, owner_id)

    return response.json({
        'success': True,
        'output': exec_out,
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

    async with DomainRemoveCtx(request, domain_id):
        await request.app.db.execute("""
        DELETE FROM domain_owners
        WHERE domain_id = $1
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
    return response.json(
        await get_domain_info(request.app.db, domain_id)
    )


@bp.get('/api/admin/domains')
@admin_route
async def get_domain_stats_all(request, admin_id):
    """Request information about all domains"""
    domain_ids = await request.app.db.fetch("""
    SELECT domain_id
    FROM domains
    ORDER BY domain_id ASC
    """)

    domain_ids = [r[0] for r in domain_ids]

    res = {}

    for domain_id in domain_ids:
        info = await get_domain_info(request.app.db, domain_id)
        res[domain_id] = info

    return response.json(res)
