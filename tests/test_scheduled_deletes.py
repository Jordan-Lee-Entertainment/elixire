# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from api.models import File, Shorten
from api.scheduled_deletes import ScheduledDeleteQueue
from .common import png_data

pytestmark = pytest.mark.asyncio


async def test_existing_file(test_cli_user):
    elixire_file = await test_cli_user.create_file("test.png", png_data(), "image/png")

    resp = await test_cli_user.put(
        f"/api/files/{elixire_file.id}/scheduled_deletion",
        query_string={"retention_time": "PT3S"},
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    async with test_cli_user.app.app_context():
        prewait_file = await File.fetch(elixire_file.id)
        assert prewait_file is not None

    job_id = rjson["job_id"]
    await ScheduledDeleteQueue.wait_job(job_id)

    async with test_cli_user.app.app_context():
        postwait_file = await File.fetch(elixire_file.id)
        assert postwait_file is not None
        assert postwait_file.deleted


async def test_existing_shorten(test_cli_user):
    shorten = await test_cli_user.create_shorten()

    resp = await test_cli_user.put(
        f"/api/shortens/{shorten.id}/scheduled_deletion",
        query_string={"retention_time": "PT3S"},
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    async with test_cli_user.app.app_context():
        prewait_shorten = await Shorten.fetch(shorten.id)
        assert prewait_shorten is not None

    job_id = rjson["job_id"]
    await ScheduledDeleteQueue.wait_job(job_id)

    async with test_cli_user.app.app_context():
        postwait_shorten = await Shorten.fetch(shorten.id)
        assert postwait_shorten is not None
        assert postwait_shorten.deleted
