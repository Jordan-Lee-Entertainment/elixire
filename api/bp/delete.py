# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import List

from quart import Blueprint, jsonify, request, current_app as app
from hail import Flake
from violet import JobQueue

from api.common.auth import token_check, password_check
from api.errors import BadInput
from api.schema import (
    validate,
    PURGE_ALL_BASE_SCHEMA,
    PURGE_ALL_SCHEMA,
    isotimestamp_or_int,
)
from api.models import Domain, File, Shorten


bp = Blueprint("files", __name__)
log = logging.getLogger(__name__)


async def _mass_shorten_delete(user_id: int, shorten_ids: List[int]):
    for shorten_id in shorten_ids:
        shorten = await Shorten.fetch(shorten_id)
        assert shorten is not None
        await shorten.delete()


@bp.route("/purge_all_content", methods=["POST"])
async def purge_all_content():
    """selectively delete content from the user."""
    user_id = await token_check()
    raw = await request.get_json()
    j = validate(raw, PURGE_ALL_SCHEMA)
    await password_check(user_id, j["password"])

    raw.pop("password")

    # semantic validation
    if "delete_from_domain" in j:
        domain = await Domain.fetch(j["delete_from_domain"])
        if domain is None:
            raise BadInput("Invalid domain ID")

    job_id = await MassDeleteQueue.submit(user_id, raw)
    return jsonify({"job_id": job_id})


class FakeCtx:
    __slots__ = "args"

    def __init__(self, user_id, query):
        self.args = (user_id, query)


@bp.route("/compute_purge_all", methods=["GET"])
async def compute_purge_all_content():
    """Calculate the total amount of files to be deleted"""
    user_id = await token_check()
    raw = dict(request.args)
    validate(raw, PURGE_ALL_BASE_SCHEMA)

    ctx = FakeCtx(user_id, raw)
    file_count, shorten_count = await MassDeleteQueue.handle(ctx, delete_content=False)
    return jsonify({"file_count": file_count, "shorten_count": shorten_count})


class MassDeleteQueue(JobQueue):
    """Delete files en-masse for a user."""

    name = "mass_delete_queue"
    args = ("user_id", "query")

    @classmethod
    def map_persisted_row(cls, row):
        return row["user_id"], row["query"]

    @classmethod
    async def submit(cls, user_id: int, query: dict, **kwargs) -> Flake:
        return await cls._sched.raw_push(cls, (user_id, query), **kwargs)

    @classmethod
    async def handle(cls, ctx, *, delete_content: bool = True):
        user_id, raw = ctx.args
        base_args = [user_id]

        domain_where = "true"
        if "delete_from_domain" in raw:
            domain_where = "domain = $2"
            base_args.append(raw["delete_from_domain"])

        file_args = list(base_args)
        shorten_args = list(base_args)

        j = {}
        _fields = (
            "delete_files_before",
            "delete_files_after",
            "delete_shortens_before",
            "delete_shortens_after",
        )

        file_wheres: List[str] = []
        shorten_wheres: List[str] = []

        # The algorithm here is confusing, but the rundown is that this is
        # dynamically generating SQL expressions for the WHERE clause in
        # our starting SELECT depending of the delete selectors
        # (delete_files_before, etc) in the route input.

        # This already takes care of selecting the right column depending of the
        # type of the selector's value (since they can be snowflakes OR timestamps),
        # as well as the necessary $N indexing in the statement

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

        col_file = "file_id" if delete_content else "COUNT(file_id)"
        col_shorten = "shorten_id" if delete_content else "COUNT(shorten_id)"
        order_by_file = "order by file_id desc" if delete_content else ""
        order_by_shorten = "order by shorten_id desc" if delete_content else ""

        file_stmt = f"""
            SELECT {col_file}
            FROM files
            WHERE uploader = $1 AND {domain_where} AND {" AND ".join(file_wheres)}
            {order_by_file}
            """

        shorten_stmt = f"""
            SELECT {col_shorten}
            FROM shortens
            WHERE uploader = $1 AND {domain_where} {" AND ".join(shorten_wheres)}
            ORDER BY shorten_id ASC
            {order_by_shorten}
            """

        if not delete_content:
            file_count = (
                await app.db.fetchval(file_stmt, *file_args) if file_wheres else 0
            )
            shorten_count = (
                await app.db.fetchval(shorten_stmt, *shorten_args)
                if shorten_wheres
                else 0
            )
            return file_count, shorten_count

        log.info("job %s got selectors %r", ctx.job_id, j)

        if file_wheres:
            file_ids = [r["file_id"] for r in await app.db.fetch(file_stmt, *file_args)]
            log.info("job %s got %d files", ctx.job_id, len(file_ids))

            await File.delete_many(file_ids, user_id=user_id)

        if shorten_wheres:
            shorten_ids = [
                r["shorten_id"] for r in await app.db.fetch(shorten_stmt, *shorten_args)
            ]
            log.info("job %s got %d shortens", ctx.job_id, len(shorten_ids))

            await _mass_shorten_delete(user_id, shorten_ids)


@bp.route("/files/<shortname>", methods=["DELETE"])
@bp.route("/files/<shortname>/delete", methods=["GET"])
async def delete_single(shortname: str):
    """Delete a single file."""
    user_id = await token_check()
    elixire_file = await File.fetch_by_with_uploader(user_id, shortname=shortname)

    # really want to keep this up.
    assert elixire_file.uploader_id == user_id
    await elixire_file.delete()
    return "", 204


@bp.route("/shortens/<shorten_name>", methods=["DELETE"])
async def shortendelete_handler(user_id, shorten_name):
    """Invalidate a shorten."""
    user_id = await token_check()
    shorten = await Shorten.fetch_by_with_uploader(user_id, shortname=shorten_name)
    await shorten.delete()
    return "", 204
