# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from quart import current_app as app
from violet.models import QueueJobContext
from api.models import File, Shorten


log = logging.getLogger(__name__)


async def scheduled_delete_handler(
    ctx: QueueJobContext, resource_type: str, resource_id: int
) -> None:
    assert resource_type in ("file", "shorten")
    log.info("Got %r %d to be deleted", resource_type, resource_id)

    # await app.sched.set_job_state(ctx.job_id, {})

    if resource_type == "file":
        resource = await File.fetch(resource_id)
    elif resource_type == "shorten":
        resource = await Shorten.fetch(resource_id)

    if resource is None:
        return

    ctx.set_start()

    log.info("Resource %r %d successfully deleted", resource_type, resource_id)
    await resource.delete()
