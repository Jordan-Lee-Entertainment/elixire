# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import secrets
from .common import png_data


async def check_exists(test_cli, shortname, not_exists=False):
    """Check if a file exists, given the shortname, token, etc."""
    resp = await test_cli.get("/api/list?page=0")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["files"], dict)

    if not_exists:
        assert shortname not in rjson["files"]
    else:
        assert shortname in rjson["files"]


async def _test_upload_png(test_cli_user):
    """Test that the upload route works given test data"""
    # file uploads not available yet.
    # https://gitlab.com/pgjones/quart/issues/147
    resp = await test_cli_user.post(
        "/api/upload",
        headers={"content-type": "multipart/form-data"},
        form={"file": (png_data(), "random.png"), "content-type": "image/png"},
    )

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    assert isinstance(respjson["delete_url"], str)
    await check_exists(test_cli_user, respjson["shortname"])


@pytest.mark.asyncio
async def _test_delete_file(test_cli_user):
    # TODO file
    resp = await test_cli_user.post("/api/upload")

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    await check_exists(test_cli_user, respjson["shortname"])

    # test delete
    short = respjson["shortname"]

    resp_del = await test_cli_user.delete(f"/api/files/{short}")
    assert resp_del.status_code == 204
    await check_exists(test_cli_user, respjson["shortname"], True)


@pytest.mark.asyncio
async def test_delete_nonexist(test_cli_user):
    """Test deletions of files that don't exist."""
    rand_file = secrets.token_hex(20)

    resp_del = await test_cli_user.delete(f"/api/files/{rand_file}")
    assert resp_del.status_code == 404

    # ensure sharex compatibility endpoint works too
    resp_del = await test_cli_user.get(f"/api/files/{rand_file}/delete")
    assert resp_del.status_code == 404
