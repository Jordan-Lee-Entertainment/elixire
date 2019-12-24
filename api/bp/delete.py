# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import List

from quart import Blueprint, jsonify, request, current_app as app

from api.common import delete_file, delete_shorten
from api.common.auth import token_check, password_check
from api.errors import BadInput  # , JobExistsError
from api.schema import validate, DELETE_ALL_SCHEMA, isotimestamp_or_int

from api.common.domain import get_domain_info

# from api.common.user import mass_file_delete

bp = Blueprint("files", __name__)
log = logging.getLogger(__name__)


@bp.route("/delete_all", methods=["POST"])
async def delete_all():
    """Delete all files for the user"""
    user_id = await token_check()
    raw = await request.get_json()
    j = validate(raw, DELETE_ALL_SCHEMA)
    await password_check(user_id, j["password"])

    raw.pop("password")

    # semantic validation
    if "delete_on_domain" in j:
        domain = await get_domain_info(j["delete_on_domain"])
        if domain is None:
            raise BadInput("Invalid domain ID")

    job_id = await app.sched.push_queue("mass_delete", (user_id, raw))
    return jsonify({"job_id": job_id})


async def mass_delete_handler(ctx, user_id, raw: dict):
    base_args = [user_id]

    domain_where = "true"
    if "delete_on_domain" in raw:
        domain_where = "domain = $2"
        base_args.append(raw["delete_on_domain"])

    file_args = list(base_args)
    shorten_args = list(base_args)

    # The algorithm here is confusing, but the rundown is that this is
    # dynamically generating SQL expressions for the WHERE clause in
    # our starting SELECT.

    j = {}
    _fields = (
        "delete_files_before",
        "delete_files_after",
        "delete_shortens_before",
        "delete_shortens_after",
    )

    file_wheres: List[str] = []
    shorten_wheres: List[str] = []

    for field in _fields:
        if field not in raw:
            continue

        j[field] = isotimestamp_or_int(raw[field])

        wheres, args, prefix = (
            (file_wheres, file_args, "file")
            if "files" in field
            else (shorten_wheres, shorten_args, "shorten")
        )

        compare_symbol = ">=" if field.endswith("after") else "<="
        column = (
            f"{prefix}_id"
            if isinstance(j[field], int)
            else f"snowflake_time({prefix}_id)"
        )

        wheres.append(f"{column} {compare_symbol} ${len(args) + 1}")
        args.append(j[field])

    file_stmt = f"""
        SELECT file_id
        FROM files
        WHERE uploader = $1 AND {domain_where} AND {" AND ".join(file_wheres)}
        ORDER BY file_id ASC
        """

    shorten_stmt = f"""
        SELECT shorten_id
        FROM shortens
        WHERE uploader = $1 AND {domain_where} {" AND ".join(shorten_wheres)}
        ORDER BY shorten_id ASC
        """

    print(file_stmt)
    print("args", file_args)
    print(shorten_stmt)
    print("args", file_args)

    file_ids = (
        []
        if not file_wheres
        else [r["file_id"] for r in await app.db.fetch(file_stmt, *file_args)]
    )
    print(file_ids)

    shorten_ids = (
        []
        if not shorten_wheres
        else [r["shorten_id"] for r in await app.db.fetch(shorten_stmt, *shorten_args)]
    )
    print(shorten_ids)


@bp.route("/files/<shortname>", methods=["DELETE"])
@bp.route("/files/<shortname>/delete", methods=["GET"])
async def delete_single(shortname):
    """Delete a single file."""
    user_id = await token_check()
    await delete_file(shortname, user_id)
    return "", 204


@bp.route("/shortens/<shorten_name>", methods=["DELETE"])
async def shortendelete_handler(user_id, shorten_name):
    """Invalidate a shorten."""
    user_id = await token_check()
    await delete_shorten(shorten_name, user_id)
    return "", 204
