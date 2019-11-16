# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from math import ceil
from typing import List

from quart import Blueprint, jsonify, current_app as app, request

from api.schema import (
    validate,
    ADMIN_MODIFY_DOMAIN,
    ADMIN_SEND_DOMAIN_EMAIL,
    ADMIN_PUT_DOMAIN,
)
from api.common.domain import (
    create_domain,
    delete_domain,
    set_domain_tags,
    create_domain_tag,
    delete_domain_tag,
)
from api.common.auth import token_check, check_admin
from api.common.email import send_email_to_user
from api.common.pagination import Pagination
from api.errors import BadInput

from api.bp.admin.audit_log_actions.domain import (
    DomainAddAction,
    DomainEditAction,
    DomainRemoveAction,
)

from api.bp.admin.audit_log_actions.email import DomainOwnerNotifyAction

from api.common.domain import get_domain_info, set_domain_owner

bp = Blueprint("admin_domain", __name__)


@bp.route("", methods=["PUT"])
async def add_domain():
    """Add a domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    j = await request.get_json()

    j = validate(await request.get_json(), ADMIN_PUT_DOMAIN)
    domain = j["domain"]

    kwargs = dict(permissions=j["permissions"])

    if "tags" in j:
        kwargs.update(tags=j["tags"])

    if "owner_id" in j:
        kwargs.update(owner_id=j["owner_id"])

    domain_id = await create_domain(domain, **kwargs)

    async with DomainAddAction() as action:
        action.update(domain_id=domain_id)

        try:
            owner_id = j["owner_id"]
            action.update(owner_id=owner_id)
        except KeyError:
            pass

    return jsonify({"success": True, "new_id": domain_id})


async def _patch_domain_handler(domain_id: int, j: dict) -> List[str]:
    fields: List[str] = []

    if "owner_id" in j:
        await set_domain_owner(domain_id, j["owner_id"])
        fields.append("owner_id")
        j.pop("owner_id")

    if "tags" in j:
        await set_domain_tags(domain_id, j["tags"])
        fields.append("tags")
        j.pop("tags")

    # the other available field is permissions. we keep this for loop to
    # future proof other fields being added to domains.
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


@bp.route("/<int:domain_id>", methods=["PATCH"])
async def patch_domain(domain_id: int):
    """Patch a domain's information"""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    j = validate(await request.get_json(), ADMIN_MODIFY_DOMAIN)

    async with DomainEditAction(request, domain_id):
        fields = await _patch_domain_handler(domain_id, j)
        return jsonify({"updated": fields})


@bp.route("/email/<int:domain_id>", methods=["POST"])
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

        user_email = await send_email_to_user(owner_id, subject, body)

    return jsonify({"owner_id": owner_id, "owner_email": user_email})


@bp.route("/<int:domain_id>/owner", methods=["PUT"])
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


@bp.route("/<int:domain_id>", methods=["DELETE"])
async def remove_domain(domain_id: int):
    """Remove a domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    async with DomainRemoveAction(request, domain_id):
        results = await delete_domain(domain_id)

    return jsonify({"success": True, **results})


@bp.route("/<int:domain_id>", methods=["GET"])
async def get_domain_stats(domain_id: int):
    """Get information about a domain."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    # TODO return 404 when not found instead of null
    return jsonify(await get_domain_info(domain_id))


@bp.route("", methods=["GET"])
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
        info = await get_domain_info(domain_id)
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


@bp.route("/search", methods=["GET"])
async def domains_search():
    """Search for domains"""
    admin_id = await token_check()
    await check_admin(admin_id, True)

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


@bp.route("/tag", methods=["PUT"])
async def create_tag():
    admin_id = await token_check()
    await check_admin(admin_id, True)

    j = validate(await request.get_json(), {"label": {"type": "string"}})
    tag_id = await create_domain_tag(j["label"])
    return jsonify({"id": tag_id})


@bp.route("/tag/<int:tag_id>", methods=["DELETE"])
async def delete_tag(tag_id: int):
    admin_id = await token_check()
    await check_admin(admin_id, True)

    await delete_domain_tag(tag_id)
    return "", 204
