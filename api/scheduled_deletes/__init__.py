# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, List, Type

import asyncpg
from quart import current_app as app, request

from api.models import Resource, File
from api.errors import NotFound
from .queue import ScheduledDeleteQueue
from .helpers import (
    validate_request_duration,
    extract_scheduled_timestamp,
)

__all__ = [
    "ScheduledDeleteQueue",
    "validate_request_duration",
    "extract_scheduled_timestamp",
    "revoke_resource_deletion",
    "fetch_deletions",
    "modify_resource_deletion",
]


async def fetch_deletions(
    resource_type: Type[Resource], user_id: int, before: int, after: int, limit: int
) -> List[asyncpg.Record]:
    if resource_type is File:
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
        WHERE {id_column} <= $2 AND {id_column} >= $3 AND
            {order_by} IS NOT NULL
        ORDER BY {order_by} DESC
        LIMIT $4
        """,
        user_id,
        before,
        after,
        limit,
    )


async def revoke_resource_deletion(resource_type, *args, user_id, **kwargs):
    """delete the scheduled deletion timestamp of a given resource
    by the value given on the request's ``retention_time`` query parameter.

    To guarantee consistency that users wouldn't be able to delete
    deletions of any resource, ``fetcher_coroutine`` MUST error accordingly.
    """
    resource = await resource_type.fetch(*args, **kwargs)
    if not resource or resource.uploader_id != user_id:
        raise NotFound(f"{type(resource).__name__} not found")

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


async def modify_resource_deletion(resource_type, *args, user_id: int, **kwargs):
    """Modify the scheduled deletion timestamp of a given resource
    by the value given on the request's ``retention_time`` query parameter.

    To guarantee consistency that users wouldn't be able to modify
    deletions of any resource, ``fetcher_coroutine`` MUST error accordingly.
    """
    validate_request_duration(required=True)

    resource = await resource_type.fetch(*args, **kwargs)
    if not resource or resource.uploader_id != user_id:
        raise NotFound(f"{type(resource).__name__} not found.")

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
