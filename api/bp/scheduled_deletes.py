# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, current_app as app, jsonify

from api.common.auth import token_check
from api.scheduled_deletes import (
    ScheduledDeleteQueue,
    validate_request_duration,
    maybe_schedule_deletion,
)
from api.models import File, Shorten


bp = Blueprint("scheduled_deletes", __name__)
log = logging.getLogger(__name__)


async def schedule_resource_deletion(fetcher_coroutine, user_id: int, **kwargs):
    validate_request_duration(required=True)

    # make sure the file exists and uploader matches before
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
        Shorten.fetch_by_with_uploader(shorten_id=shorten_id),
        user_id,
        shorten_id=shorten_id,
    )
