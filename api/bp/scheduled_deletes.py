# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import Optional
from enum import Enum

from quart import Blueprint, current_app as app, jsonify, request

from api.common.auth import token_check
from api.scheduled_deletes import (
    ScheduledDeleteQueue,
    validate_request_duration,
    maybe_schedule_deletion,
    extract_scheduled_timestamp,
)
from api.models import File, Shorten
from api.errors import NotFound
from api.common.pagination import Pagination


bp = Blueprint("scheduled_deletes", __name__)
log = logging.getLogger(__name__)


class WantedResource(Enum):
    files = "file"
    shortens = "shorten"


@bp.route("/scheduled_deletions")
async def list_scheduled_deletions():
    user_id = await token_check()
    wanted_resource = WantedResource(request.args["resource_type"])
    pagination = Pagination()

    resource_table = "files" if wanted_resource == WantedResource.File else "shortens"
    rows = await app.db.fetch(
        f"""
        SELECT *
        FROM scheduled_deletion_queue
        JOIN {resource_table} ON {resource_table}.uploader_id = $1
        ORDER BY file_id DESC
        ORDER BY shorten_id DESC
        LIMIT $2
        OFFSET ($3::integer * $2::integer)
        """,
        user_id,
        pagination.per_page,
        pagination.page,
    )

    return jsonify(rows)


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

    column = None
    if file_id is not None:
        column = "file_id"
    elif shorten_id is not None:
        column = "shorten_id"

    assert column is not None

    _, new_scheduled_at = extract_scheduled_timestamp(request.args["retention_time"])
    job_id = await app.db.fetchval(
        f"""
        UPDATE scheduled_delete_queue
        SET scheduled_at = $2
        WHERE {column} = $1 AND state = 0
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
