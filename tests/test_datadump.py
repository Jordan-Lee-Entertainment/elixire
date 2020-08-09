# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import json
import zipfile
import logging
import pytest
from urllib.parse import parse_qs

from violet import JobState

from tests.common.utils import extract_first_url
from tests.common.generators import png_data
from api.bp.datadump.janitor import dump_janitor
from api.bp.datadump import DatadumpQueue

pytestmark = pytest.mark.asyncio

log = logging.getLogger(__name__)


async def test_datadump(test_cli_user):
    shorten = await test_cli_user.create_shorten()
    image_file = png_data()
    elixire_file = await test_cli_user.create_file("test.jpg", image_file, "image/png")

    resp = await test_cli_user.post("/api/dump")
    assert resp.status_code == 200

    zipdump = None

    try:
        rjson = await resp.json
        assert isinstance(rjson, dict)
        assert isinstance(rjson["job_id"], str)
        job_id = rjson["job_id"]
        filename = f"{test_cli_user['user_id']}_{test_cli_user['username']}.zip"
        path = os.path.join(test_cli_user.app.econfig.DUMP_FOLDER, filename)

        resp = await test_cli_user.get("/api/dump")
        assert resp.status_code == 200
        rjson = await resp.json
        assert isinstance(rjson, dict)
        assert isinstance(rjson["results"], list)
        assert rjson["results"]
        assert rjson["results"][0]["job_id"] == job_id
        assert isinstance(rjson["pagination"], dict)
        assert "total" in rjson["pagination"]
        assert "current" in rjson["pagination"]

        await test_cli_user.app.sched.wait_job_start(job_id, timeout=20)

        resp = await test_cli_user.get("/api/profile")
        assert resp.status_code == 200
        rjson = await resp.json
        assert "dump_status" in rjson
        dump = rjson["dump_status"]
        assert isinstance(rjson["dump_status"], dict)
        assert dump["state"] == "processing"
        assert dump["job_id"] == job_id

        await DatadumpQueue.wait_job(job_id, timeout=20)

        status = await DatadumpQueue.fetch_job_status(job_id)
        assert status.state == JobState.Completed
        assert not status.errors

        # TODO check email, and then see if /get gives the actual dump
        email = test_cli_user.app._email_list[-1]
        url = extract_first_url(email["content"])
        dump_token = parse_qs(url.query)["key"][0]

        resp = await test_cli_user.get(
            "/api/dump/get", query_string={"key": dump_token}
        )
        assert resp.status_code == 200

        # TODO: better testing of the zip file, e.g files (but we need to
        # upload stuff, etc, its hard
        zipdump = zipfile.ZipFile(path, "r")
        with zipdump.open("user_data.json") as user_data_file:
            user_data = json.load(user_data_file)
            assert user_data["id"] == test_cli_user.user["user_id"]

        with zipdump.open("shortens.json") as shortens_file:
            shortens = json.load(shortens_file)
            assert any(s for s in shortens if s["shorten_id"] == shorten.id)

        with zipdump.open("files.json") as files_file:
            files = json.load(files_file)
            assert any(f for f in files if f["file_id"] == elixire_file.id)

        with zipdump.open(
            f"files/{elixire_file.id}_{elixire_file.shortname}.png"
        ) as raw_file:
            assert raw_file
            assert raw_file.read() == image_file.getvalue()

        zip_stat = os.stat(path)
        os.utime(path, times=(zip_stat.st_atime, zip_stat.st_mtime - 22600))
        async with test_cli_user.app.app_context():
            await dump_janitor()
        assert not os.path.exists(path)

    finally:
        if zipdump:
            zipdump.close()

        try:
            os.unlink(path)
        except Exception as err:
            log.warning("failed to remove test user dump file: %r", err)
