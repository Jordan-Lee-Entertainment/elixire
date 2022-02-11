# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import os
import json
import zipfile
import logging
import pytest
from urllib.parse import parse_qs
from pathlib import Path

from api.bp.datadump.tasks import dump_janitor

from tests.test_upload import png_request
from tests.util.helpers import extract_first_url
from tests.common import login_normal

pytestmark = pytest.mark.asyncio

log = logging.getLogger(__name__)


async def upload_test_png(test_cli, utoken: str):
    kwargs = png_request()
    kwargs["headers"]["authorization"] = utoken
    resp = await test_cli.post(
        "/api/upload",
        **kwargs,
    )
    assert resp.status_code == 200
    return await resp.json


async def create_test_shorten(test_cli, utoken: str):
    resp = await test_cli.post(
        "/api/shorten",
        headers={"Authorization": utoken},
        json={"url": "https://elixi.re"},
    )
    assert resp.status_code == 200
    return await resp.json


async def wait_for_finished_dump(app, current_email_count):
    count = 0
    while True:
        if count > 5:
            raise AssertionError("Timed out waiting for dump results")
        if len(app._test_email_list) > current_email_count:
            break
        await asyncio.sleep(1)
        count += 1


async def test_datadump(test_cli):
    utoken = await login_normal(test_cli)

    # -- cleanup test user
    profile_resp = await test_cli.get("/api/profile", headers={"authorization": utoken})
    assert profile_resp.status_code == 200
    profile_json = await profile_resp.json
    await test_cli.app.db.execute(
        "delete from current_dump_state where user_id = $1",
        int(profile_json["user_id"]),
    )
    await test_cli.app.db.execute(
        "delete from email_dump_tokens where user_id = $1",
        int(profile_json["user_id"]),
    )

    # know the datadump path beforehand so we know which file to possibly delete
    normal_user_id = profile_json["user_id"]
    filename = f"{normal_user_id}_{profile_json['username']}.zip"
    zip_path = Path(test_cli.app.econfig.DUMP_FOLDER) / filename

    # -- add file and shorten to test user
    elixire_file = await upload_test_png(test_cli, utoken)
    elixire_shorten = await create_test_shorten(test_cli, utoken)

    current_email_count = len(test_cli.app._test_email_list)
    resp = await test_cli.post("/api/dump/request", headers={"authorization": utoken})
    assert resp.status_code == 200

    zipdump = None

    try:
        await wait_for_finished_dump(test_cli.app, current_email_count)

        email = test_cli.app._test_email_list[-1]
        url = extract_first_url(email["body"])
        dump_token = parse_qs(url.query)["key"][0]

        resp = await test_cli.get("/api/dump_get", query_string={"key": dump_token})
        assert resp.status_code == 200

        zipdump = zipfile.ZipFile(zip_path, "r")
        with zipdump.open("user_data.json") as user_data_file:
            user_data = json.load(user_data_file)
            assert user_data["user_id"] == profile_json["user_id"]

        with zipdump.open("shortens.json") as shortens_file:
            shortens = json.load(shortens_file)
            assert any(
                s for s in shortens if s["filename"] == elixire_shorten["shortname"]
            )

        with zipdump.open("files.json") as files_file:
            files = json.load(files_file)
            found_file = next(
                f for f in files if f["filename"] == elixire_file["shortname"]
            )

        with zipdump.open(
            f"files/{found_file['file_id']}_{found_file['filename']}.png"
        ) as raw_file:
            assert raw_file
            # TODO
            # assert raw_file.read() == image_file.getvalue()

        zip_stat = os.stat(zip_path)
        os.utime(zip_path, times=(zip_stat.st_atime, zip_stat.st_mtime - 22600))
        async with test_cli.app.app_context():
            await dump_janitor()
        assert not zip_path.exists()
    finally:
        if zipdump:
            zipdump.close()

        try:
            zip_path.unlink()
        except Exception as err:
            log.exception("failed to remove test user dump file: %r", err)
