# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from math import ceil
from typing import List

from quart import Blueprint, jsonify, current_app as app, request

from api.schema import validate, ADMIN_MODIFY_DOMAIN, ADMIN_SEND_DOMAIN_EMAIL
from api.common.auth import token_check, check_admin
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


@bp.route("/api/admin/domains", methods=["PUT"])
async def add_domain():
    """Add a domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    j = await request.get_json()

    # TODO use validate()
    domain_name = str(j["domain"])
    is_adminonly = bool(j["admin_only"])
    is_official = bool(j["official"])
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
                owner_id,
            )

    keys = solve_domain(domain_name)
    await app.storage.raw_invalidate(*keys)

    return jsonify({"success": True, "result": result, "new_id": domain_id})


async def _patch_domain_handler(domain_id: int, j: dict) -> List[str]:
    fields: List[str] = []

    if "owner_id" in j:
        await app.db.execute(
            """
            INSERT INTO domain_owners (domain_id, user_id)
            VALUES ($1, $2)
            ON CONFLICT ON CONSTRAINT domain_owners_pkey
            DO UPDATE
                SET user_id = $2
                WHERE domain_owners.domain_id = $1
            """,
            domain_id,
            j["owner_id"],
        )

        fields.append("owner_id")
        j.pop("owner_id")

    # the other available fields are admin_only, official, and permissions.
    # all of those follow the same sql query, so we can just write a for loop
    # to process them
    for field, value in j.items():
        await app.db.execute(
            f"""
            UPDATE domains
            SET {field} = $1
            WHERE domain_id = $2
            """,
            value,
            domain_id,
        )

        fields.append(field)

    return fields


@bp.route("/api/admin/domains/<int:domain_id>", methods=["PATCH"])
async def patch_domain(domain_id: int):
    """Patch a domain's information"""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    j = validate(await request.get_json(), ADMIN_MODIFY_DOMAIN)

    async with DomainEditAction(request, domain_id):
        fields = await _patch_domain_handler(domain_id, j)
        return jsonify({"updated": fields})


@bp.route("/api/admin/email_domain/<int:domain_id>", methods=["POST"])
async def email_domain(domain_id: int):
    admin_id = await token_check()
    await check_admin(admin_id, True)

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

        resp_tup, user_email = await send_user_email(app, owner_id, subject, body)

    resp, _ = resp_tup

    return jsonify(
        {"success": resp.status == 200, "owner_id": owner_id, "owner_email": user_email}
    )


@bp.route("/api/admin/domains/<int:domain_id>/owner", methods=["PUT"])
async def add_owner(domain_id: int):
    """Add an owner to a single domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)
    j = await request.get_json()

    try:
        owner_id = int(j["owner_id"])
    except (ValueError, KeyError):
        raise BadInput("Invalid number for owner ID")

    async with DomainEditAction(request, domain_id):
        exec_out = await app.db.execute(
            """
        INSERT INTO domain_owners (domain_id, user_id)
        VALUES ($1, $2)
        """,
            domain_id,
            owner_id,
        )

    return jsonify({"success": True, "output": exec_out})


@bp.route("/api/admin/domains/<int:domain_id>", methods=["DELETE"])
async def remove_domain(domain_id: int):
    """Remove a domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

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

    async with DomainRemoveAction(request, domain_id):
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


@bp.route("/api/admin/domains/<int:domain_id>")
async def get_domain_stats(domain_id: int):
    """Get information about a domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    return jsonify(await get_domain_info(app.db, domain_id))


@bp.route("/api/admin/domains")
async def get_domain_stats_all():
    """Request information about all domains"""
    admin_id = await token_check()
    await check_admin(admin_id, True)

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
        info = await get_domain_info(app.db, domain_id)
        res[domain_id] = info

    total_count = 0 if not domain_ids else domain_ids[0]["total_count"]

    # page being -1 serves as a signal that the client
    # isn't paginated, so we shouldn't even add the extra
    # pagination-specific fields.
    extra = (
        {}
        if page == -1
        else {"pagination": {"total": ceil(total_count / per_page), "current": page}}
    )

    return jsonify({**res, **extra})


@bp.route("/api/admin/domains/search")
async def domains_search():
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
        results[domain_id] = await get_domain_info(app.db, domain_id)

    total_count = 0 if not domain_ids else domain_ids[0]["total_count"]
    return jsonify(pagination.response(results, total_count=total_count))
