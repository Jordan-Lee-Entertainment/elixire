# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import io
import os
import time
import asyncio
import pytest
import os.path
from pathlib import Path
from urllib.parse import urlparse


from quart.testing import make_test_body_with_headers
from quart.datastructures import FileStorage

from .common import png_data, hexs
from api.common import thumbnail_janitor_tick

pytestmark = pytest.mark.asyncio


async def check_exists(test_cli, shortname, deleted: bool = False):
    """Check if a file exists, given the shortname, token, etc.

    Set `deleted` to true to verify if a file is actually deleted
    """
    resp = await test_cli.get("/api/list?page=0")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["files"], dict)

    if deleted:
        assert shortname not in rjson["files"]
        return
    else:
        assert shortname in rjson["files"]
        elixire_file = rjson["files"][shortname]
        assert elixire_file["size"] > 0

    url = urlparse(elixire_file["url"])
    _, extension = os.path.splitext(url.path.split("/")[-1])

    relative_image_path = f"/i/{shortname}{extension}"
    # check the file is available on the domain+subdomain it was uploaded on
    resp = await test_cli.get(
        relative_image_path, do_token=False, headers={"host": url.netloc}
    )
    assert resp.status_code == 200
    assert url.netloc in resp.headers["access-control-allow-origin"]

    # check the file isn't available on other domains
    resp = await test_cli.get(
        relative_image_path, do_token=False, headers={"host": "undefined.com"}
    )
    assert resp.status_code == 404

    # check thumbnail can be generated successfully
    resp = await test_cli.get(
        f"/t/s{shortname}{extension}", do_token=False, headers={"host": url.netloc}
    )
    assert resp.status_code == 200

    # check that Discordbot receives html
    resp = await test_cli.get(
        relative_image_path,
        do_token=False,
        headers={"host": url.netloc, "user-agent": "Discordbot"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/html"
    response_text = (await resp.get_data()).decode()
    assert "twitter" in response_text

    # check that Discordbot receives html (on thumbnails too)
    # TODO(quart): port v3 thumbnailing behavior to here
    #
    # resp = await test_cli.get(
    #     f"/t/s{shortname}{extension}",
    #     headers={"host": url.netloc, "user-agent": "Discordbot"},
    # )
    # assert resp.status_code == 200
    # assert resp.headers["content-type"] == "text/html"
    # response_text = (await resp.get_data()).decode()
    # assert "twitter" in response_text

    # -- test HEAD and Ranged requests to the file
    resp = await test_cli.head(
        relative_image_path, do_token=False, headers={"host": url.netloc}
    )
    assert resp.status_code == 200

    resp = await test_cli.get(
        relative_image_path,
        do_token=False,
        headers={"host": url.netloc, "range": "bytes=0-9"},
    )
    assert resp.status_code == 206
    assert resp.headers["content-length"] == "10"


def png_request(data=None):
    data = data or png_data()
    body, headers = make_test_body_with_headers(
        files={
            "file": FileStorage(
                stream=data,
                filename=f"{hexs(10)}.png",
                name="file",
                content_type="image/png",
            )
        }
    )

    return {"data": body, "headers": headers}


async def test_upload_png(test_cli_user, test_cli_admin):
    """Test that the upload route works given test data"""
    kwargs = png_request()
    resp = await test_cli_user.post(
        "/api/upload",
        **kwargs,
    )

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    assert isinstance(respjson["delete_url"], str)

    shortname = respjson["shortname"]
    await check_exists(test_cli_user, shortname)

    # -- test fetching file on admin api
    resp = await test_cli_admin.get(f"/api/admin/file/{shortname}")
    assert resp.status_code == 200
    rjson = await resp.json
    assert rjson["filename"] == shortname


async def test_delete_file(test_cli_user):
    kwargs = png_request()
    resp = await test_cli_user.post("/api/upload", **kwargs)

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    await check_exists(test_cli_user, respjson["shortname"])

    # test delete
    resp_del = await test_cli_user.delete(
        "/api/delete",
        json={"filename": respjson["shortname"]},
    )

    assert resp_del.status_code == 200
    rdel_json = await resp_del.json
    assert isinstance(rdel_json, dict)
    assert rdel_json["success"]

    await check_exists(test_cli_user, respjson["shortname"], True)


async def test_delete_all_files(test_cli_user):
    kwargs = png_request()
    resp = await test_cli_user.post("/api/upload", **kwargs)

    assert resp.status_code == 200
    respjson = await resp.json

    resp = await test_cli_user.post(
        "/api/delete_all",
        json={"password": test_cli_user.user["password"]},
    )

    assert resp.status_code == 200
    rjson_deleteall = await resp.json
    assert rjson_deleteall["success"]

    await asyncio.wait_for(
        test_cli_user.app.sched.jobs[f'delete_files_{test_cli_user.user["user_id"]}'],
        timeout=5,
    )

    await check_exists(test_cli_user, respjson["shortname"], deleted=True)


async def test_delete_nonexist(test_cli_user):
    resp_del = await test_cli_user.delete(
        "/api/delete",
        json={"filename": "lkdjklfjkgkghkkhsfklhjslkdfjglakdfjl"},
    )

    assert resp_del.status_code == 404


EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


async def test_eicar_upload(test_cli_user):
    if not test_cli_user.app.econfig.UPLOAD_SCAN:
        pytest.skip("upload scans disabled")
        return

    # without this, asyncio subprocess just hangs on communicate(), even
    # though the process already finished. its so fuckin weird
    #
    # fix found on https://github.com/python/asyncio/issues/478#issuecomment-268476438
    asyncio.get_child_watcher().attach_loop(test_cli_user.app.loop)

    test_cli_user.app.econfig.SCAN_WAIT_THRESHOLD = 5

    kwargs = png_request(data=io.BytesIO(EICAR.encode()))
    resp = await test_cli_user.post(
        "/api/upload",
        **kwargs,
    )
    assert resp.status_code == 415


async def test_upload_random_domain(test_cli_user):
    kwargs = png_request()
    resp = await test_cli_user.post(
        "/api/upload",
        **kwargs,
    )

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    assert isinstance(respjson["delete_url"], str)

    shortname = respjson["shortname"]
    await check_exists(test_cli_user, shortname)


async def test_thumbnail_janitor(test_cli_user):
    kwargs = png_request()
    resp = await test_cli_user.post("/api/upload", **kwargs)

    assert resp.status_code == 200
    respjson = await resp.json

    # TODO use Path
    url = urlparse(respjson["url"])
    _, extension = os.path.splitext(url.path.split("/")[-1])

    shortname = respjson["shortname"]

    filesystem_thumbnail_path = Path(test_cli_user.app.econfig.THUMBNAIL_FOLDER) / (
        "s" + shortname + extension
    )

    api_thumbnail_path = f"/t/s{shortname}{extension}"
    resp_thumbnail = await test_cli_user.get(
        api_thumbnail_path, do_token=False, headers={"host": url.netloc}
    )
    assert resp_thumbnail.status_code == 200

    very_old_mtime = time.time() - (60 * 60)
    os.utime(filesystem_thumbnail_path, (very_old_mtime, very_old_mtime))

    assert filesystem_thumbnail_path.exists()
    async with test_cli_user.app.app_context():
        await thumbnail_janitor_tick()
    assert not filesystem_thumbnail_path.exists()
