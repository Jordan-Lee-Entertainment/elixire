# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, jsonify, request

from api.common.auth import token_check
from api.scheduled_deletes import (
    validate_request_duration,
    modify_resource_deletion,
    revoke_resource_deletion,
    fetch_deletions,
)
from api.models import File, Shorten, User
from api.errors import NotFound, BadInput
from api.common.pagination import lazy_paginate


bp = Blueprint("scheduled_deletes", __name__)
log = logging.getLogger(__name__)


@bp.route("/scheduled_deletions")
async def list_scheduled_deletions():
    user_id = await token_check()
    resource_type = {"file": File, "shorten": Shorten}.get(
        request.args["resource_type"]
    )
    if not resource_type:
        raise BadInput("Invalid resource type (expected 'file' or 'shorten')")
    before, after, limit = lazy_paginate()

    rows = await fetch_deletions(resource_type, user_id, before, after, limit)
    return jsonify({"jobs": [dict(r) for r in rows]})


@bp.route("/files/<int:file_id>/scheduled_deletion")
async def fetch_file_deletion(file_id: int):
    user_id = await token_check()

    rows = await fetch_deletions(File, user_id, file_id, file_id, 1)
    if not rows:
        raise NotFound("No scheduled deletion jobs found for the given file.")

    assert len(rows) == 1
    return {"job": dict(rows[0])}


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion")
async def fetch_shorten_deletion(shorten_id: int):
    user_id = await token_check()

    rows = await fetch_deletions(Shorten, user_id, shorten_id, shorten_id, 1)
    if not rows:
        raise NotFound("No scheduled deletion jobs found for the given shorten.")

    assert len(rows) == 1
    return {"job": dict(rows[0])}


async def schedule_resource_deletion(resource_type, *args, user_id: int, **kwargs):
    """Schedule a resource deletion from the current request."""
    validate_request_duration(required=True)

    resource = await resource_type.fetch(*args, **kwargs)
    if not resource or resource.uploader_id != user_id:
        raise NotFound(f"{type(resource).__name__} not found.")

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
    return await schedule_resource_deletion(File, user_id=user_id, file_id=file_id)


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion", methods=["PUT"])
async def schedule_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await schedule_resource_deletion(
        Shorten, user_id=user_id, shorten_id=shorten_id
    )


@bp.route("/files/<int:file_id>/scheduled_deletion", methods=["PATCH"])
async def modify_file_deletion(file_id: int):
    user_id = await token_check()
    return await modify_resource_deletion(File, user_id=user_id, file_id=file_id)


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion", methods=["PATCH"])
async def modify_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await modify_resource_deletion(
        Shorten, user_id=user_id, shorten_id=shorten_id
    )


@bp.route("/files/<int:file_id>/scheduled_deletion", methods=["DELETE"])
async def revoke_file_deletion(file_id: int):
    user_id = await token_check()
    return await revoke_resource_deletion(File, user_id=user_id, file_id=file_id)


@bp.route("/shortens/<int:shorten_id>/scheduled_deletion", methods=["DELETE"])
async def revoke_shorten_deletion(shorten_id: int):
    user_id = await token_check()
    return await revoke_resource_deletion(
        Shorten, user_id=user_id, shorten_id=shorten_id,
    )
