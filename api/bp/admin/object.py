# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncpg

from quart import Blueprint, jsonify, request, current_app as app

from api.common import delete_file, delete_shorten
from api.schema import validate, ADMIN_MODIFY_FILE
from api.errors import BadInput, NotFound
from api.decorators import admin_route

from api.bp.admin.audit_log_actions.object import ObjectEditAction, ObjectDeleteAction

from api.common.fetch import OBJ_MAPPING

bp = Blueprint("admin_object", __name__)


async def _handler_object(obj_type: str, obj_fname: str):
    """Handler for fetching files/shortens."""
    id_handler, obj_handler = OBJ_MAPPING[obj_type]
    obj_id = await id_handler(obj_fname)
    if obj_id is None:
        raise NotFound("Object not found")

    return jsonify(await obj_handler(obj_id))


@bp.get("/file/<shortname>")
@admin_route
async def get_file_by_name(_admin_id, shortname):
    """Get a file's information by shortname."""
    return await _handler_object("file", shortname)


@bp.get("/shorten/<shortname>")
@admin_route
async def get_shorten_by_name(_admin_id, shortname):
    """Get a shorten's information by shortname."""
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

        # Invalidate based on the query
        to_invalidate = "fspath" if obj_type == "file" else "redir"
        to_invalidate = f"{to_invalidate}:{old_domain}:{obj_name}"

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
            *[
                f"fspath:{old_domain}:{obj_name}",
                f"fspath:{old_domain}:{new_shortname}",
            ]
        )

        updated.append("shortname")

    return jsonify(updated)


@bp.patch("/file/<int:file_id>")
@admin_route
async def modify_file(_admin_id, file_id):
    """Modify file information."""

    async with ObjectEditAction(file_id, "file"):
        return await handle_modify("file", file_id)


@bp.patch("/shorten/<int:shorten_id>")
@admin_route
async def modify_shorten(_admin_id, shorten_id):
    """Modify file information."""

    async with ObjectEditAction(shorten_id, "shorten"):
        return await handle_modify("shorten", shorten_id)


@bp.delete("/file/<int:file_id>")
@admin_route
async def delete_file_handler(_admin_id, file_id):
    """Delete a file."""
    row = await app.db.fetchrow(
        """
    SELECT filename, uploader
    FROM files
    WHERE file_id = $1
    """,
        file_id,
    )

    if row is None:
        raise BadInput("File not found")

    async with ObjectDeleteAction(file_id, "file"):
        await delete_file(row["filename"], row["uploader"])

    return jsonify(
        {
            "shortname": row["filename"],
            "uploader": str(row["uploader"]),
            "success": True,
        }
    )


@bp.delete("/shorten/<int:shorten_id>")
@admin_route
async def delete_shorten_handler(_admin_id, shorten_id: int):
    """Delete a shorten."""
    row = await app.db.fetchrow(
        """
    SELECT filename, uploader
    FROM shortens
    WHERE shorten_id = $1
    """,
        shorten_id,
    )

    if row is None:
        raise BadInput("Shorten not found")

    async with ObjectDeleteAction(shorten_id, "shorten"):
        await delete_shorten(row["filename"], row["uploader"])

    return jsonify(
        {
            "shortname": row["filename"],
            "uploader": str(row["uploader"]),
            "success": True,
        }
    )
