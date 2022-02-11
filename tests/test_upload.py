# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import os.path
from urllib.parse import urlparse


from quart.testing import make_test_body_with_headers
from quart.datastructures import FileStorage

from .common import login_normal, login_admin, png_data, hexs

pytestmark = pytest.mark.asyncio


async def check_exists(test_cli, shortname, utoken, not_exists=False):
    """Check if a file exists, given the shortname, token, etc."""
    resp = await test_cli.get(
        "/api/list?page=0",
        headers={
            "Authorization": utoken,
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["files"], dict)

    if not_exists:
        assert shortname not in rjson["files"]
        return
    else:
        assert shortname in rjson["files"]
        elixire_file = rjson["files"][shortname]

    url = urlparse(elixire_file["url"])
    _, extension = os.path.splitext(url.path.split("/")[-1])

    relative_image_path = f"/i/{shortname}{extension}"
    # check the file is available on the domain+subdomain it was uploaded on
    resp = await test_cli.get(relative_image_path, headers={"host": url.netloc})
    assert resp.status_code == 200

    # check the file isn't available on other domains
    resp = await test_cli.get(relative_image_path, headers={"host": "undefined.com"})
    assert resp.status_code == 404

    # check thumbnail can be generated successfully
    resp = await test_cli.get(
        f"/t/s{shortname}{extension}", headers={"host": url.netloc}
    )
    assert resp.status_code == 200

    # check that Discordbot receives html
    resp = await test_cli.get(
        relative_image_path,
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
    resp = await test_cli.head(relative_image_path, headers={"host": url.netloc})
    assert resp.status_code == 200

    resp = await test_cli.get(
        relative_image_path, headers={"host": url.netloc, "range": "bytes=0-9"}
    )
    assert resp.status_code == 206
    assert resp.headers["content-length"] == "10"


def png_request():
    body, headers = make_test_body_with_headers(
        files={
            "file": FileStorage(
                stream=png_data(),
                filename=f"{hexs(10)}.png",
                name="file",
                content_type="image/png",
            )
        }
    )

    return {"data": body, "headers": headers}


async def test_upload_png(test_cli):
    """Test that the upload route works given test data"""
    utoken = await login_normal(test_cli)
    kwargs = png_request()
    kwargs["headers"]["authorization"] = utoken
    resp = await test_cli.post(
        "/api/upload",
        **kwargs,
    )

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    assert isinstance(respjson["delete_url"], str)

    shortname = respjson["shortname"]
    await check_exists(test_cli, shortname, utoken)

    # -- test fetching file on admin api
    atoken = await login_admin(test_cli)
    resp = await test_cli.get(
        f"/api/admin/file/{shortname}",
        headers={"authorization": atoken},
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert rjson["filename"] == shortname


async def test_delete_file(test_cli):
    utoken = await login_normal(test_cli)
    kwargs = png_request()
    kwargs["headers"]["authorization"] = utoken
    resp = await test_cli.post("/api/upload", **kwargs)

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    await check_exists(test_cli, respjson["shortname"], utoken)

    # test delete
    resp_del = await test_cli.delete(
        "/api/delete",
        headers={"Authorization": utoken},
        json={"filename": respjson["shortname"]},
    )

    assert resp_del.status_code == 200
    rdel_json = await resp_del.json
    assert isinstance(rdel_json, dict)
    assert rdel_json["success"]

    await check_exists(test_cli, respjson["shortname"], utoken, True)


async def test_delete_nonexist(test_cli):
    utoken = await login_normal(test_cli)
    resp_del = await test_cli.delete(
        "/api/delete",
        headers={"Authorization": utoken},
        json={"filename": "lkdjklfjkgkghkkhsfklhjslkdfjglakdfjl"},
    )

    assert resp_del.status_code == 404
