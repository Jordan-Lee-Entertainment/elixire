# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import Optional
from enum import Enum

from quart import Blueprint, current_app as app, jsonify, request

from api.common.auth import token_check
from api.scheduled_deletes import (
    validate_request_duration,
    maybe_schedule_deletion,
    extract_scheduled_timestamp,
)
from api.models import File, Shorten
from api.errors import NotFound
from api.common.pagination import lazy_paginate


bp = Blueprint("scheduled_deletes", __name__)
log = logging.getLogger(__name__)


class WantedResource(Enum):
    files = "file"
    shortens = "shorten"


@bp.route("/scheduled_deletions")
async def list_scheduled_deletions():
    user_id = await token_check()
    wanted_resource = WantedResource(request.args["resource_type"])
    before, after, limit = lazy_paginate()

    if wanted_resource == WantedResource.File:
        resource_table = "files"
        id_column = "file_id"
    else:
        resource_table = "shortens"
        id_column = "shorten_id"

    rows = await app.db.fetch(
        f"""
        SELECT job_id, state, errors, inserted_at, scheduled_at,
               file_id, shorten_id
        FROM scheduled_deletion_queue
        JOIN {resource_table} ON {resource_table}.uploader_id = $1
        WHERE {id_column} < $2 AND {id_column} > $3
        ORDER BY {id_column} DESC
        LIMIT $4
        """,
        user_id,
        before,
        after,
        limit,
    )

    return jsonify({"jobs": rows})


async def schedule_resource_deletion(fetcher_coroutine, user_id: int, **kwargs):
    validate_request_duration(required=True)

    # make sure the resource exists and uploader matches before
    # scheduling a deletion. method raises NotFound on any mishaps
    # so it will be fine.
    _ = await fetcher_coroutine

    # job_id can't be none because we require retention_time
    # on the validation call. because of that, we also always
    # ignore the user setting for default max retention. this does
    # make the route a little bit more expensive.
    #
    # TODO: investigate if we can put a flag on maybe_schedule_deletion
    # so it doesn't request user settings when it isn't required.
    job_id = await maybe_schedule_deletion(user_id, **kwargs)
    assert job_id is not None
    return jsonify({"job_id": job_id})


@bp.route("/files/<file_id>/scheduled_deletion", methods=["PUT"])
async def schedule_file_deletion(file_id: int):
    user_id = await token_check()
    return await schedule_resource_deletion(
        File.fetch_by_with_uploader(user_id, file_id=file_id), user_id, file_id=file_id
    )


@bp.route("/shortens/<shorten_id>/scheduled_deletion", methods=["PUT"])
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


@bp.route("/files/<file_id>/scheduled_deletion", methods=["PATCH"])
async def modify_file_deletion(file_id: int):
    user_id = await token_check()
    return await modify_resource_deletion(
        File.fetch_by_with_uploader(user_id, file_id=file_id), user_id, file_id=file_id
    )


@bp.route("/shortens/<shorten_id>/scheduled_deletion", methods=["PATCH"])
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


@bp.route("/files/<file_id>/scheduled_deletion", methods=["DELETE"])
async def revoke_file_deletion(file_id: int):
    user_id = await token_check()
    return await revoke_resource_deletion(
        File.fetch_by_with_uploader(user_id, file_id=file_id), user_id, file_id=file_id
    )


@bp.route("/shortens/<shorten_id>/scheduled_deletion", methods=["DELETE"])
async def revoke_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await revoke_resource_deletion(
        Shorten.fetch_by_with_uploader(user_id, shorten_id=shorten_id),
        user_id,
        shorten_id=shorten_id,
    )
