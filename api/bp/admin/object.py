# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncpg

from quart import Blueprint, current_app as app, request, jsonify

from api.common.auth import token_check, check_admin
from api.schema import validate, ADMIN_MODIFY_FILE
from api.errors import BadInput, NotFound

from api.bp.admin.audit_log_actions.object import ObjectEditAction, ObjectDeleteAction

from api.common.fetch import OBJ_MAPPING
from api.models import File, Shorten

bp = Blueprint("admin_object", __name__)


async def _handler_object(obj_type: str, obj_fname: str):
    """Handler for fetching files/shortens."""
    # TODO: make the action classes use file/shorten models directly
    if obj_type == "file":
        resource_type = File
    elif obj_type == "shorten":
        resource_type = Shorten
    else:
        raise TypeError("Object type specified in Action is invalid.")

    resource = await resource_type.fetch_by(shortname=obj_fname)
    if resource is None:
        raise NotFound("{obj_type} not found")

    return jsonify(resource.to_dict())


@bp.route("/file/<shortname>")
async def get_file_by_name(shortname: str):
    """Get a file's information by shortname."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    return await _handler_object("file", shortname)


@bp.route("/shorten/<shortname>")
async def get_shorten_by_name(shortname: str):
    """Get a shorten's information by shortname."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    return await _handler_object("shorten", shortname)


async def handle_modify(obj_type: str, obj_id: int):
    """Generic function to work with files OR shortens."""
    table = "files" if obj_type == "file" else "shortens"
    field = "file_id" if obj_type == "file" else "shorten_id"

    payload = validate(await request.get_json(), ADMIN_MODIFY_FILE)

    new_domain = payload.get("domain_id")
    new_shortname = payload.get("shortname")

    updated = []

    row = await app.db.fetchrow(
        f"""
        SELECT filename, domain
        FROM {table}
        WHERE {field} = $1
        """,
        obj_id,
    )

    obj_name = row["filename"]
    old_domain = row["domain"]

    if new_domain is not None:
        try:
            await app.db.execute(
                f"""
                UPDATE {table}
                SET domain = $1
                WHERE {field} = $2
                """,
                new_domain,
                obj_id,
            )
        except asyncpg.ForeignKeyViolationError:
            raise BadInput("Unknown domain ID")

        # we're invalidating instead of set_with_ttl because it is supposed
        # to be used on hot paths. this is not a hot path
        prefix = "fspath" if obj_type == "file" else "redir"
        to_invalidate = f"{prefix}:{old_domain}:{obj_name}"
        await app.storage.raw_invalidate(to_invalidate)

        updated.append("domain")

    if new_shortname is not None:
        # Ignores deleted files, just sets the new filename
        try:
            await app.db.execute(
                f"""
                UPDATE {table}
                SET filename = $1
                WHERE {field} = $2
                """,
                new_shortname,
                obj_id,
            )
        except asyncpg.UniqueViolationError:
            raise BadInput("Shortname already exists.")

        # Invalidate both old and new
        await app.storage.raw_invalidate(
            *[f"fspath:{old_domain}:{obj_name}", f"fspath:{old_domain}:{new_shortname}"]
        )

        updated.append("shortname")

    # TODO move to {"updated": updated}
    return jsonify(updated)


@bp.route("/file/<int:file_id>", methods=["PATCH"])
async def modify_file(file_id: int):
    """Modify file information."""

    admin_id = await token_check()
    await check_admin(admin_id, True)

    async with ObjectEditAction(request, file_id, "file"):
        return await handle_modify("file", file_id)


@bp.route("/shorten/<int:shorten_id>", methods=["PATCH"])
async def modify_shorten(shorten_id: int):
    """Modify file information."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    async with ObjectEditAction(request, shorten_id, "shorten"):
        return await handle_modify("shorten", shorten_id)


@bp.route("/file/<int:file_id>", methods=["DELETE"])
async def delete_file_handler(file_id: int):
    """Delete a file."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    elixire_file = await File.fetch(file_id)

    if elixire_file is None:
        raise BadInput("File not found")

    async with ObjectDeleteAction(request, file_id, "file"):
        await elixire_file.delete()

    return jsonify(elixire_file.to_dict())


@bp.route("/shorten/<int:shorten_id>", methods=["DELETE"])
async def delete_shorten_handler(shorten_id: int):
    """Delete a shorten."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    shorten = await Shorten.fetch(shorten_id)
    if shorten is None:
        raise BadInput("Shorten not found")

    async with ObjectDeleteAction(request, shorten_id, "shorten"):
        await shorten.delete()

    return jsonify(shorten.to_dict())
