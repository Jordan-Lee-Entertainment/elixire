# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import Optional, List
from enum import Enum

import asyncpg
from quart import Blueprint, current_app as app, jsonify, request

from api.common.auth import token_check
from api.scheduled_deletes import (
    validate_request_duration,
    extract_scheduled_timestamp,
)
from api.models import File, Shorten, User
from api.errors import NotFound
from api.common.pagination import lazy_paginate


bp = Blueprint("scheduled_deletes", __name__)
log = logging.getLogger(__name__)


class WantedResource(Enum):
    files = "file"
    shortens = "shorten"


async def fetch_deletions(
    wanted_resource: WantedResource, user_id: int, before: int, after: int, limit: int
) -> List[asyncpg.Record]:
    if wanted_resource == WantedResource.files:
        resource_table = "files"
        id_column = "files.file_id"
        order_by = "scheduled_delete_queue.file_id"
    else:
        resource_table = "shortens"
        id_column = "shortens.shorten_id"
        order_by = "scheduled_delete_queue.shorten_id"

    return await app.db.fetch(
        f"""
        SELECT job_id, state, errors, inserted_at, scheduled_at,
               scheduled_delete_queue.file_id,
               scheduled_delete_queue.shorten_id
        FROM scheduled_delete_queue
        JOIN {resource_table} ON {resource_table}.uploader = $1
        WHERE {id_column} < $2 AND {id_column} > $3 AND
            {order_by} IS NOT NULL
        ORDER BY {order_by} DESC
        LIMIT $4
        """,
        user_id,
        before,
        after,
        limit,
    )


@bp.route("/scheduled_deletions")
async def list_scheduled_deletions():
    user_id = await token_check()
    wanted_resource = WantedResource(request.args["resource_type"])
    before, after, limit = lazy_paginate()

    rows = await fetch_deletions(wanted_resource, user_id, before, after, limit)
    return jsonify({"jobs": [dict(r) for r in rows]})


@bp.route("/files/<int:file_id>/scheduled_deletion")
async def fetch_file_deletion(file_id: int):
    user_id = await token_check()

    # XXX: file_id -1 and + 1?
    rows = await fetch_deletions(WantedResource.files, user_id, file_id, file_id, 1)
    if not rows:
        raise NotFound("No scheduled deletion jobs found for the given file.")

    assert len(rows) == 1
    return {"job": dict(rows[0])}


async def schedule_resource_deletion(fetcher_coroutine, user_id: int, **kwargs):
    validate_request_duration(required=True)

    # make sure the resource exists and uploader matches before
    # scheduling a deletion. method raises NotFound on any mishaps
    # so it will be fine.
    resource = await fetcher_coroutine

    # job_id can't be none because we require retention_time
    # on the validation call. because of that, we also always
    # ignore the user setting for default max retention. this does
    # make the route a little bit more expensive.
    #
    # TODO: investigate if we can put a flag on maybe_schedule_deletion
    # so it doesn't request user settings when it isn't required to do so.

    if resource.uploader_id != user_id:
        raise NotFound("Resource not found.")

    user = await User.fetch(user_id)
    assert user is not None

    job_id = await user.schedule_deletion_for(
        resource, duration=request.args["retention_time"]
    )
    assert job_id is not None
    return jsonify({"job_id": job_id})


@bp.route("/files/<int:file_id>/scheduled_deletion", methods=["PUT"])
async def schedule_file_deletion(file_id: int):
    user_id = await token_check()
    return await schedule_resource_deletion(
        File.fetch_by_with_uploader(user_id, file_id=file_id), user_id, file_id=file_id
    )


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion", methods=["PUT"])
async def schedule_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await schedule_resource_deletion(
        Shorten.fetch_by_with_uploader(user_id, shorten_id=shorten_id),
        user_id,
        shorten_id=shorten_id,
    )


async def modify_resource_deletion(fetcher_coroutine, user_id, **kwargs):
    """Modify the scheduled deletion timestamp of a given resource
    by the value given on the request's ``retention_time`` query parameter.

    To guarantee consistency that users wouldn't be able to modify
    deletions of any resource, ``fetcher_coroutine`` MUST error accordingly.
    """
    validate_request_duration(required=True)
    _ = await fetcher_coroutine

    # try to find a job that matches the wanted resource
    file_id: Optional[int] = kwargs.get("file_id")
    shorten_id: Optional[int] = kwargs.get("shorten_id")
    assert file_id or shorten_id
    resource_id: int = file_id or shorten_id

    _, new_scheduled_at = extract_scheduled_timestamp(request.args["retention_time"])

    # There are chances for SQL optimization here at the cost of code
    # readability. We know which one of the columns we'll use on this query
    # by checking either of file_id or shorten_id aren't None.
    #
    # The cost difference between doing ({column} = $1) compared to
    # (file_id = $1 OR shorten_id = $1) was minimal (even though the former
    # was less cost), but I don't have enough data to assert which one
    # would be better.
    #
    # For now I chose code readability as the thing that counts here. If we
    # go hellish on SQL, we can optimize this, and make it very clear why
    # we're doing so
    job_id = await app.db.fetchval(
        """
        UPDATE scheduled_delete_queue
        SET scheduled_at = $2
        WHERE (file_id = $1 OR shorten_id = $1) AND state = 0
        RETURNING job_id
        """,
        resource_id,
        new_scheduled_at,
    )

    if job_id is None:
        # TODO: maybe this error is too generic?
        raise NotFound("There were no jobs found for the given resource.")

    return "", 204


@bp.route("/files/<int:file_id>/scheduled_deletion", methods=["PATCH"])
async def modify_file_deletion(file_id: int):
    user_id = await token_check()
    return await modify_resource_deletion(
        File.fetch_by_with_uploader(user_id, file_id=file_id), user_id, file_id=file_id
    )


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion", methods=["PATCH"])
async def modify_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await modify_resource_deletion(
        Shorten.fetch_by_with_uploader(user_id, shorten_id=shorten_id),
        user_id,
        shorten_id=shorten_id,
    )


async def revoke_resource_deletion(fetcher_coroutine, user_id, **kwargs):
    """delete the scheduled deletion timestamp of a given resource
    by the value given on the request's ``retention_time`` query parameter.

    To guarantee consistency that users wouldn't be able to delete
    deletions of any resource, ``fetcher_coroutine`` MUST error accordingly.
    """
    _ = await fetcher_coroutine

    # try to delete a job that matches the wanted resource
    file_id: Optional[int] = kwargs.get("file_id")
    shorten_id: Optional[int] = kwargs.get("shorten_id")
    assert file_id or shorten_id
    resource_id: int = file_id or shorten_id

    job_id = await app.db.fetchval(
        """
        DELETE FROM scheduled_delete_queue
        WHERE (file_id = $1 OR shorten_id = $1) AND state = 0
        RETURNING job_id
        """,
        resource_id,
    )

    if job_id is None:
        raise NotFound("There were no jobs found for the given resource.")

    return "", 204


@bp.route("/files/<int:file_id>/scheduled_deletion", methods=["DELETE"])
async def revoke_file_deletion(file_id: int):
    user_id = await token_check()
    return await revoke_resource_deletion(
        File.fetch_by_with_uploader(user_id, file_id=file_id), user_id, file_id=file_id
    )


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion", methods=["DELETE"])
async def revoke_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await revoke_resource_deletion(
        Shorten.fetch_by_with_uploader(user_id, shorten_id=shorten_id),
        user_id,
        shorten_id=shorten_id,
    )
