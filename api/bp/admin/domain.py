# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from math import ceil

from quart import Blueprint, request, current_app as app, jsonify

from api.schema import validate, ADMIN_MODIFY_DOMAIN, ADMIN_SEND_DOMAIN_EMAIL
from api.decorators import admin_route
from api.common.email import send_user_email
from api.common.pagination import Pagination
from api.storage import solve_domain
from api.errors import BadInput

from api.bp.admin.audit_log_actions.domain import (
    DomainAddAction,
    DomainEditAction,
    DomainRemoveAction,
)

from api.bp.admin.audit_log_actions.email import DomainOwnerNotifyAction

from api.common.domain import get_domain_info

bp = Blueprint("admin_domain", __name__)


@bp.put("/domains")
@admin_route
async def add_domain(admin_id: int):
    """Add a domain."""
    j = await request.get_json()
    domain_name = str(j["domain"])
    is_adminonly = bool(j["admin_only"])
    is_official = bool(j["official"])

    # default 3
    permissions = int(j.get("permissions", 3))

    db = app.db

    result = await db.execute(
        """
    INSERT INTO domains
        (domain, admin_only, official, permissions)
    VALUES
        ($1, $2, $3, $4)
    """,
        domain_name,
        is_adminonly,
        is_official,
        permissions,
    )

    domain_id = await db.fetchval(
        """
    SELECT domain_id
    FROM domains
    WHERE domain = $1
    """,
        domain_name,
    )

    async with DomainAddAction() as action:
        action.update(domain_id=domain_id)

        if "owner_id" in j:
            owner_id = int(j["owner_id"])
            action.update(owner_id=owner_id)

            await db.execute(
                """
            INSERT INTO domain_owners (domain_id, user_id)
            VALUES ($1, $2)
            """,
                domain_id,
                int(j["owner_id"]),
            )

    keys = solve_domain(domain_name)
    await app.storage.raw_invalidate(*keys)

    return jsonify(
        {
            "success": True,
            "result": result,
            "new_id": domain_id,
        }
    )


async def _dp_check(
    db, domain_id: int, payload: dict, updated_fields: list, field: str
):
    """Check a field inside the payload and update it if it exists."""

    if field in payload:
        await db.execute(
            f"""
        UPDATE domains
        SET {field} = $1
        WHERE domain_id = $2
        """,
            payload[field],
            domain_id,
        )

        updated_fields.append(field)


@bp.patch("/domains/<int:domain_id>")
@admin_route
async def patch_domain(admin_id: int, domain_id: int):
    """Patch a domain's information"""
    payload = validate(await request.get_json(), ADMIN_MODIFY_DOMAIN)

    updated_fields = []
    db = app.db

    async with DomainEditAction(domain_id):
        if "owner_id" in payload:
            exec_out = await db.execute(
                """
            UPDATE domain_owners
            SET user_id = $1
            WHERE domain_id = $2
            """,
                int(payload["owner_id"]),
                domain_id,
            )

            if exec_out != "UPDATE 0":
                updated_fields.append("owner_id")

        # since we're passing updated_fields which is a reference to the
        # list, it can be mutaded and it will propagate into this function.
        await _dp_check(db, domain_id, payload, updated_fields, "admin_only")
        await _dp_check(db, domain_id, payload, updated_fields, "official")
        await _dp_check(db, domain_id, payload, updated_fields, "permissions")

    return jsonify(
        {
            "updated": updated_fields,
        }
    )


@bp.post("/email_domain/<int:domain_id>")
@admin_route
async def email_domain(admin_id: int, domain_id: int):
    payload = validate(await request.get_json(), ADMIN_SEND_DOMAIN_EMAIL)
    subject, body = payload["subject"], payload["body"]

    owner_id = await app.db.fetchval(
        """
    SELECT user_id
    FROM domain_owners
    WHERE domain_id = $1
    """,
        domain_id,
    )

    if owner_id is None:
        raise BadInput("Domain Owner not found")

    async with DomainOwnerNotifyAction() as action:
        action.update(
            domain_id=domain_id, owner_id=owner_id, subject=subject, body=body
        )

        resp_tup, user_email = await send_user_email(owner_id, subject, body)

    resp, _ = resp_tup

    return jsonify(
        {
            "success": resp.status == 200,
            "owner_id": owner_id,
            "owner_email": user_email,
        }
    )


@bp.put("/domains/<int:domain_id>/owner")
@admin_route
async def add_owner(admin_id: int, domain_id: int):
    """Add an owner to a single domain."""
    j = await request.get_json()
    try:
        owner_id = int(j["owner_id"])
    except (ValueError, KeyError):
        raise BadInput("Invalid number for owner ID")

    async with DomainEditAction(domain_id):
        exec_out = await app.db.execute(
            """
        INSERT INTO domain_owners (domain_id, user_id)
        VALUES ($1, $2)
        """,
            domain_id,
            owner_id,
        )

    return jsonify(
        {
            "success": True,
            "output": exec_out,
        }
    )


@bp.delete("/domains/<int:domain_id>")
@admin_route
async def remove_domain(admin_id: int, domain_id: int):
    """Remove a domain."""
    domain_name = await app.db.fetchval(
        """
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """,
        domain_id,
    )

    files_count = await app.db.execute(
        """
    UPDATE files set domain = 0 WHERE domain = $1
    """,
        domain_id,
    )

    shorten_count = await app.db.execute(
        """
    UPDATE shortens set domain = 0 WHERE domain = $1
    """,
        domain_id,
    )

    users_count = await app.db.execute(
        """
    UPDATE users set domain = 0 WHERE domain = $1
    """,
        domain_id,
    )

    users_shorten_count = await app.db.execute(
        """
    UPDATE users set shorten_domain = 0 WHERE shorten_domain = $1
    """,
        domain_id,
    )

    async with DomainRemoveAction(domain_id):
        await app.db.execute(
            """
        DELETE FROM domain_owners
        WHERE domain_id = $1
        """,
            domain_id,
        )

        result = await app.db.execute(
            """
        DELETE FROM domains
        WHERE domain_id = $1
        """,
            domain_id,
        )

    keys = solve_domain(domain_name)
    await app.storage.raw_invalidate(*keys)

    return jsonify(
        {
            "success": True,
            "file_move_result": files_count,
            "shorten_move_result": shorten_count,
            "users_move_result": users_count,
            "users_shorten_move_result": users_shorten_count,
            "result": result,
        }
    )


@bp.get("/domains/<int:domain_id>")
@admin_route
async def get_domain_stats(admin_id, domain_id):
    """Get information about a domain."""
    return jsonify(await get_domain_info(domain_id))


@bp.get("/domains")
@admin_route
async def get_domain_stats_all(_admin_id):
    """Request information about all domains"""
    args = request.args
    per_page = int(args.get("per_page", 20))

    try:
        page = int(args["page"])

        if page < 0:
            raise BadInput("Negative page not allowed.")

        domain_ids = await app.db.fetch(
            f"""
        SELECT domain_id, COUNT(*) OVER() as total_count
        FROM domains
        ORDER BY domain_id ASC
        LIMIT {per_page}
        OFFSET ($1 * {per_page})
        """,
            page,
        )
    except KeyError:
        page = -1
        domain_ids = await app.db.fetch(
            """
        SELECT domain_id, COUNT(*) OVER() as total_count
        FROM domains
        ORDER BY domain_id ASC
        """
        )
    except ValueError:
        raise BadInput("Invalid page number")

    res = {}

    for row in domain_ids:
        domain_id = row["domain_id"]
        info = await get_domain_info(domain_id)
        res[domain_id] = info

    total_count = 0 if not domain_ids else domain_ids[0]["total_count"]

    # page being -1 serves as a signal that the client
    # isn't paginated, so we shouldn't even add the extra
    # pagination-specific fields.
    extra = (
        {}
        if page == -1
        else {
            "pagination": {
                "total": ceil(total_count / per_page),
                "current": page,
            },
        }
    )

    return jsonify({**res, **extra})


@bp.get("/domains/search")
@admin_route
async def domains_search(admin_id):
    """Search for domains"""
    args = request.args
    pagination = Pagination()

    query = args.get("query")

    domain_ids = await app.db.fetch(
        """
    SELECT domain_id, COUNT(*) OVER () AS total_count
    FROM domains
    WHERE $3 = '' OR domain LIKE '%'||$3||'%'
    ORDER BY domain_id ASC
    LIMIT $2::integer
    OFFSET ($1::integer * $2::integer)
    """,
        pagination.page,
        pagination.per_page,
        query or "",
    )

    results = {}

    for row in domain_ids:
        domain_id = row["domain_id"]
        results[domain_id] = await get_domain_info(domain_id)

    total_count = 0 if not domain_ids else domain_ids[0]["total_count"]
    return jsonify(pagination.response(results, total_count=total_count))
