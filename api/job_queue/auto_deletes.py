# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import current_app as app
from violet.models import QueueJobContext


async def scheduled_delete_handler(ctx: QueueJobContext) -> None:
    await ctx.set_start()
    await app.sched.set_job_state(ctx.job_id, {})
