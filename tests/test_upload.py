# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import io
import asyncio
import os.path
from urllib.parse import urlparse

import pytest
from .common import png_request, hexs, aiohttp_form
from api.bp.delete import MassDeleteQueue
from api.models import File
from api.scheduled_deletes import ScheduledDeleteQueue

pytestmark = pytest.mark.asyncio


async def check_shorten_exists(test_cli, shortname: str, *, reverse=False):
    """Check if a shorten exists (or not) given the shortname."""
    resp = await test_cli.get("/api/shortens")
    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["shortens"], list)

    try:
        next(filter(lambda data: data["shortname"] == shortname, rjson["shortens"]))

        # if we don't want the shorten to exist but we found it,
        # that's an assertion error
        if reverse:
            raise AssertionError()
    except StopIteration:
        # if we want the shorten to exist but we DIDN't find it,
        # that's an assertion error
        if not reverse:
            raise AssertionError()

        # if we don't want the shorten to exist and we just found out it
        # actually doesn't exist, we return since the rest of the code
        # isn't for that
        return


async def check_exists(test_cli, shortname, *, reverse=False):
    """Check if a file exists (or not) given the shortname."""
    resp = await test_cli.get("/api/files")

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
            raise AssertionError(f"File found: {file!r}")
    except StopIteration:
        # if we want the file to exist but we DIDN't find it,
        # that's an assertion error
        if not reverse:
            raise AssertionError("File not found")

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

    # check thumbnail can be generated successfully
    resp = await test_cli.get(
        f"/t/s{shortname}{extension}", headers={"host": url.netloc}
    )
    assert resp.status_code == 200


async def test_upload_png(test_cli_user):
    """Test that the upload route works given test data"""
    # file uploads aren't natively available under QuartClient, see:
    # https://gitlab.com/pgjones/quart/issues/147

    # instead we use aiohttp.FormData to generate a body that is valid
    # for the post() call

    test_domain = await test_cli_user.create_domain()

    # store the request data for uploads in a variable since new calls to
    # png_request() will return new random bytes to prevent deduplication from
    # breaking other tests.
    req = await png_request()

    subdomain = hexs(10)
    resp = await test_cli_user.post(
        "/api/upload",
        **(req),
        query_string={"domain": test_domain.id, "subdomain": subdomain},
    )

    assert resp.status_code == 200
    json = await resp.json
    shortname = json["shortname"]
    assert isinstance(json, dict)
    assert isinstance(json["url"], str)
    await check_exists(test_cli_user, shortname)

    url = f"/i/{shortname}.png"

    host_without_wildcard = test_domain.domain.replace("*.", "")
    # (browsers won't be accessing "*.domain.tld", they will access "domain.tld"
    # -- "*.domain.tld" is how they are represented internally)

    # accessing on the subdomain+domain that it was uploaded to works
    host = f"{subdomain}.{host_without_wildcard}"
    resp = await test_cli_user.get(url, headers={"host": host})
    assert resp.status_code == 200

    # test HEAD and Ranged requests to the file
    resp = await test_cli_user.head(url, headers={"host": host})
    assert resp.status_code == 200

    resp = await test_cli_user.get(url, headers={"host": host, "range": "bytes=0-9"})
    assert resp.status_code == 206

    assert resp.headers["content-length"] == "10"

    # accessing on the base domain without a subdomain doesn't work
    resp = await test_cli_user.get(url, headers={"host": host_without_wildcard})
    assert resp.status_code == 404

    # accessing on the domain but with a different subdomain doesn't work
    resp = await test_cli_user.get(
        url, headers={"host": f"nope.{host_without_wildcard}"}
    )
    assert resp.status_code == 404

    # trying to upload the same file will bring the same url (deduplication)
    # we should check for that

    subdomain = hexs(10)
    resp = await test_cli_user.post(
        "/api/upload",
        **(req),
        query_string={"domain": test_domain.id, "subdomain": subdomain},
    )

    assert resp.status_code == 200
    json = await resp.json

    new_shortname = json["shortname"]
    assert new_shortname == shortname

    assert isinstance(json, dict)
    assert isinstance(json["url"], str)
    await check_exists(test_cli_user, shortname)


# Should make libmagic return application/octet-stream.
#
# We use a constant because even though we could generate 50 random bytes,
# libmagic only reads 3-4 bytes to determine file type, which means tests
# have a much higher probability of failing on this.
MAGIC_BYTES = b"\xd2\x06\x8e\x98\x87\xd5m\xc4/B"


async def test_bogus_data(test_cli_user):
    """Test that uploading random data fails."""
    test_domain = await test_cli_user.create_domain()
    request_kwargs = await aiohttp_form(
        io.BytesIO(MAGIC_BYTES), f"{hexs(10)}.bin", "application/octet-stream"
    )

    subdomain = hexs(10)
    resp = await test_cli_user.post(
        "/api/upload",
        **request_kwargs,
        query_string={"domain": test_domain.id, "subdomain": subdomain},
    )

    assert resp.status_code == 415


async def test_legacy_file_resolution(test_cli_user):
    """Upload a test file and force it to be in legacy v2 domain behavior. Then
    test that behavior is funcional."""

    test_domain = await test_cli_user.create_domain()

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

    host_without_wildcard = test_domain.domain.replace("*.", "")
    url = f"/i/{shortname}.png"

    resp = await test_cli_user.get(url, headers={"host": host_without_wildcard})
    assert resp.status_code == 200

    resp = await test_cli_user.get(
        url, headers={"host": f"subdomain.{host_without_wildcard}"}
    )
    assert resp.status_code == 200

    resp = await test_cli_user.get(url, headers={"host": "undefined.com"})
    assert resp.status_code == 404


async def _upload(test_cli_user, **kwargs) -> dict:
    resp = await test_cli_user.post("/api/upload", **(await png_request()), **kwargs)

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)
    await check_exists(test_cli_user, respjson["shortname"])

    return respjson


async def _shorten(test_cli_user, **kwargs) -> dict:
    url = "https://elixi.re"
    resp = await test_cli_user.post("/api/shorten", json={"url": url}, **kwargs)

    assert resp.status_code == 200

    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson["url"], str)

    return respjson


async def test_delete_file(test_cli_user):
    respjson = await _upload(test_cli_user)

    # test delete
    short = respjson["shortname"]

    resp_del = await test_cli_user.delete(f"/api/files/{short}")
    assert resp_del.status_code == 204
    await check_exists(test_cli_user, respjson["shortname"], reverse=True)


async def test_delete_file_many(test_cli_user):
    test_domain = await test_cli_user.create_domain()

    rjson = await _upload(test_cli_user)
    rjson2 = await _upload(test_cli_user, query_string={"domain": test_domain.id})
    rjson_shorten = await _shorten(test_cli_user)
    shortname1 = rjson["shortname"]
    shortname2 = rjson2["shortname"]
    shortname_shorten = rjson_shorten["shortname"]
    assert shortname1 != shortname2
    assert shortname1 != shortname_shorten
    assert shortname2 != shortname_shorten

    resp = await test_cli_user.get(
        "/api/compute_purge_all", query_string={"delete_files_after": 0}
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert rjson["file_count"] > 0
    assert rjson["shorten_count"] >= 0

    # assert both exist before deleting
    await check_exists(test_cli_user, shortname1)
    await check_exists(test_cli_user, shortname2)

    # delete files from the domain only, then proceed to delete all files
    # this is to make sure that specific code path works as well
    resp_del = await test_cli_user.post(
        "/api/purge_all_content",
        json={
            "password": test_cli_user["password"],
            "delete_from_domain": test_domain.id,
        },
    )
    assert resp_del.status_code == 200
    rjson = await resp_del.json
    await MassDeleteQueue.wait_job(rjson["job_id"], timeout=30)
    await check_exists(test_cli_user, shortname2, reverse=True)

    resp_del = await test_cli_user.post(
        "/api/purge_all_content",
        json={
            "password": test_cli_user["password"],
            "delete_files_after": 0,
            "delete_shortens_after": 0,
        },
    )
    assert resp_del.status_code == 200
    rjson = await resp_del.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["job_id"], str)
    assert rjson["job_id"]
    await MassDeleteQueue.wait_job(rjson["job_id"], timeout=30)

    await check_exists(test_cli_user, shortname1, reverse=True)
    await check_shorten_exists(test_cli_user, shortname_shorten, reverse=True)


async def test_delete_nonexist(test_cli_user):
    """Test deletions of files that don't exist."""
    rand_file = hexs(20)

    resp_del = await test_cli_user.delete(f"/api/files/{rand_file}")
    assert resp_del.status_code == 404

    # ensure sharex compatibility endpoint works too
    resp_del = await test_cli_user.get(f"/api/files/{rand_file}/delete")
    assert resp_del.status_code == 404


async def test_upload_ephmeral(test_cli_user):
    """Test that uploading a file with a set retention time
    actually works and will leave the file inaccessible afterwards."""
    upload = await _upload(test_cli_user, query_string={"retention_time": "PT3S"})
    await check_exists(test_cli_user, upload["shortname"])

    job_id = upload.get("scheduled_delete_job_id")
    assert job_id is not None

    status = await ScheduledDeleteQueue.fetch_job_status(job_id)
    assert status is not None

    async with test_cli_user.app.app_context():
        elixire_file = await File.fetch_by(shortname=upload["shortname"])
        assert elixire_file is not None

    resp = await test_cli_user.get(
        "/api/scheduled_deletions",
        query_string={"resource_type": "file", "after": elixire_file.id},
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    # if we just uploaded, there must be at least one job in here.
    # since the job list is ordered by file id, the first job is the one we
    # want
    assert isinstance(rjson["jobs"], list)
    job = rjson["jobs"][0]
    assert isinstance(job, dict)
    assert isinstance(job["job_id"], str)
    assert isinstance(job["state"], int)
    assert job["file_id"] == elixire_file.id

    resp = await test_cli_user.get(
        f"/api/files/{elixire_file.id}/scheduled_deletion",
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["job"], dict)

    job = rjson["job"]
    assert job["file_id"] == elixire_file.id
    assert job["shorten_id"] is None

    await ScheduledDeleteQueue.wait_job(job_id)

    await check_exists(test_cli_user, upload["shortname"], reverse=True)


EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


async def test_eicar_upload(test_cli_user):
    if not test_cli_user.app.econfig.UPLOAD_SCAN:
        return

    # uh... ok???
    # without this, asyncio subprocess kinda just hangs on communicate(), even
    # though the process already finished
    #
    # fix found on https://github.com/python/asyncio/issues/478#issuecomment-268476438
    asyncio.get_child_watcher().attach_loop(test_cli_user.app.loop)

    test_cli_user.app.econfig.SCAN_WAIT_THRESHOLD = 5

    request_kwargs = await aiohttp_form(
        io.BytesIO(EICAR.encode()), f"{hexs(10)}.txt", "text/plain"
    )

    resp = await test_cli_user.post("/api/upload", **request_kwargs)
    assert resp.status_code == 415
