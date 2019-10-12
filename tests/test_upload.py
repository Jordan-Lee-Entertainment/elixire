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
    resp = await test_cli.get("/api/files?page=0")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["files"], list)

    try:
        file = next(
            filter(
                lambda file_data: file_data["shortname"] == shortname, rjson["files"]
            )
        )

        # if we don't want the file to exist but we found it,
        # that's an assertion error
        if reverse:
            raise AssertionError()
    except StopIteration:
        # if we want the file to exist but we DIDN't find it,
        # that's an assertion error
        if not reverse:
            raise AssertionError()

        # if we don't want the file to exist and we just found out it
        # actually doesn't exist, we return since the rest of the code
        # isn't for that
        return

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


async def test_upload_png(test_cli_user, test_domain):
    """Test that the upload route works given test data"""
    # file uploads aren't natively available under QuartClient, see:
    # https://gitlab.com/pgjones/quart/issues/147

    # instead we use aiohttp.FormData to generate a body that is valid
    # for the post() call

    # TODO set to some random domain_id and subdomain for nicer testing

    subdomain = hexs(10)
    resp = await test_cli_user.post(
        "/api/upload",
        **(await png_request()),
        query_string={"domain": test_domain.id, "subdomain": subdomain},
    )

    assert resp.status_code == 200
    json = await resp.json
    shortname = json["shortname"]
    assert isinstance(json, dict)
    assert isinstance(json["url"], str)
    await check_exists(test_cli_user, shortname)

    url = f"/i/{shortname}.png"

    host_without_wildcard = test_domain.name.replace("*.", "")
    # (browsers won't be accessing "*.domain.tld", they will access "domain.tld"
    # -- "*.domain.tld" is how they are represented internally)

    # accessing on the subdomain+domain that it was uploaded to works
    resp = await test_cli_user.get(
        url, headers={"host": f"{subdomain}.{host_without_wildcard}"}
    )
    assert resp.status_code == 200

    # accessing on the base domain without a subdomain doesn't work
    resp = await test_cli_user.get(url, headers={"host": host_without_wildcard})
    assert resp.status_code == 404

    # accessing on the domain but with a different subdomain doesn't work
    resp = await test_cli_user.get(
        url, headers={"host": f"nope.{host_without_wildcard}"}
    )
    assert resp.status_code == 404


async def test_legacy_file_resolution(test_cli_user, test_domain):
    resp = await test_cli_user.post(
        "/api/upload", **(await png_request()), query_string={"domain": test_domain.id}
    )

    assert resp.status_code == 200
    json = await resp.json
    shortname = json["shortname"]

    # manually set the subdomain column to NULL, which means v2 behavior
    # (accessible on both root and subdomain)
    resp = await test_cli_user.app.db.execute(
        """
        UPDATE files
        SET subdomain = NULL
        WHERE filename = $1 AND subdomain = ''
        """,
        shortname,
    )
    assert resp == "UPDATE 1"

    host_without_wildcard = test_domain.name.replace("*.", "")
    url = f"/i/{shortname}.png"

    resp = await test_cli_user.get(url, headers={"host": host_without_wildcard})
    assert resp.status_code == 200

    resp = await test_cli_user.get(
        url, headers={"host": f"subdomain.{host_without_wildcard}"}
    )
    assert resp.status_code == 200

    resp = await test_cli_user.get(url, headers={"host": "undefined.com"})
    assert resp.status_code == 404


async def test_delete_file(test_cli_user):
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
