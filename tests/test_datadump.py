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

pytestmark = pytest.mark.asyncio

log = logging.getLogger(__name__)


async def upload_test_png(test_cli):
    kwargs = png_request()
    resp = await test_cli.post(
        "/api/upload",
        **kwargs,
    )
    assert resp.status_code == 200
    return await resp.json


async def create_test_shorten(test_cli):
    resp = await test_cli.post(
        "/api/shorten",
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
        await asyncio.sleep(0.3)
        count += 1


async def test_datadump(test_cli, test_cli_user):
    # know the datadump path beforehand so we know which file to remove
    filename = f"{test_cli_user.id}_{test_cli_user.username}.zip"
    zip_path = Path(test_cli_user.app.econfig.DUMP_FOLDER) / filename

    # -- add file and shorten to test user
    elixire_file = await upload_test_png(test_cli_user)
    elixire_shorten = await create_test_shorten(test_cli_user)

    current_email_count = len(test_cli_user.app._test_email_list)
    resp = await test_cli_user.post("/api/dump/request")
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
            assert user_data["user_id"] == str(test_cli_user.id)

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
