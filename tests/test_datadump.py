# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import os
import logging
import pytest

pytestmark = pytest.mark.asyncio

log = logging.getLogger(__name__)


async def test_profile_work(test_cli_user):
    resp = await test_cli_user.post("/api/dump/request")
    assert resp.status_code == 200

    try:
        rjson = await resp.json
        assert isinstance(rjson, dict)
        assert isinstance(rjson["job_id"], str)
        filename = f"{test_cli_user['user_id']}_{test_cli_user['username']}.zip"

        # we can't really wait for the job to complete here, so instead
        # we sleep()
        await asyncio.sleep(1.3)

        status = await test_cli_user.app.sched.fetch_queue_job_status(rjson["job_id"])
        assert status.queue_name == "datadump"
        assert not status.errors
    finally:
        try:
            path = os.path.join(test_cli_user.app.econfig.DUMP_FOLDER, filename)
            os.unlink(path)
        except Exception as err:
            log.warning("failed to remove test user dump file: %r", err)
