# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import json
import zipfile
import logging
import pytest

pytestmark = pytest.mark.asyncio

log = logging.getLogger(__name__)


async def test_datadump(test_cli_user):
    resp = await test_cli_user.post("/api/dump")
    assert resp.status_code == 200

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

        await test_cli_user.app.sched.wait_job_start(job_id)

        resp = await test_cli_user.get("/api/profile")
        assert resp.status_code == 200
        rjson = await resp.json
        assert "dump_status" in rjson
        dump = rjson["dump_status"]
        assert isinstance(rjson["dump_status"], dict)
        assert dump["state"] == "processing"
        assert dump["job_id"] == job_id

        await test_cli_user.app.sched.wait_job(job_id)

        status = await test_cli_user.app.sched.fetch_queue_job_status(job_id)
        assert status.queue_name == "datadump"
        assert not status.errors

        # TODO check email, and then see if /get gives the actual dump
        assert test_cli_user.app._email_list

        # TODO use model for test_cli_user.user
        dump_token = await test_cli_user.app.db.fetchval(
            """
            SELECT hash
            FROM email_dump_tokens
            WHERE user_id = $1
            ORDER BY expiral
            """,
            test_cli_user.user["user_id"],
        )

        assert dump_token is not None

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

    finally:
        zipdump.close()
        try:
            os.unlink(path)
        except Exception as err:
            log.warning("failed to remove test user dump file: %r", err)
