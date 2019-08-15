# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import os.path
from urllib.parse import urlparse

from .common import png_request, hexs

pytestmark = pytest.mark.asyncio


async def check_exists(test_cli, shortname, *, reverse=False):
    """Check if a file exists (or not) given the shortname."""
    resp = await test_cli.get("/api/list?page=0")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["files"], dict)

    if reverse:
        assert shortname not in rjson["files"]
        return

    assert shortname in rjson["files"]

    file = rjson["files"][shortname]
    url = urlparse(file["url"])
    _, extension = os.path.splitext(url.path.split("/")[-1])

    # check the file is available on the domain+subdomain it was uploaded on
    resp = await test_cli.get(
        f"/i/{shortname}{extension}", headers={"host": url.netloc}
    )
    assert resp.status_code == 200

    # check the file isn't available on other domains
    resp = await test_cli.get(
        f"/i/{shortname}{extension}", headers={"host": "undefined.com"}
    )
    assert resp.status_code == 404


async def test_upload_png(test_cli_user):
    """Test that the upload route works given test data"""
    # file uploads aren't natively available under QuartClient, see:
    # https://gitlab.com/pgjones/quart/issues/147

    # instead we use aiohttp.FormData to generate a body that is valid
    # for the post() call

    # TODO set to some random domain_id and subdomain for nicer testing

    resp = await test_cli_user.post("/api/upload", **(await png_request()))

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    await check_exists(test_cli_user, respjson["shortname"])

    resp = await test_cli_user.post("/api/upload", **(await png_request()))

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    await check_exists(test_cli_user, respjson["shortname"])

    # test delete
    short = respjson["shortname"]

    resp_del = await test_cli_user.delete(f"/api/files/{short}")
    assert resp_del.status_code == 204
    await check_exists(test_cli_user, respjson["shortname"], reverse=True)


async def test_delete_nonexist(test_cli_user):
    """Test deletions of files that don't exist."""
    rand_file = hexs(20)

    resp_del = await test_cli_user.delete(f"/api/files/{rand_file}")
    assert resp_del.status_code == 404

    # ensure sharex compatibility endpoint works too
    resp_del = await test_cli_user.get(f"/api/files/{rand_file}/delete")
    assert resp_del.status_code == 404
