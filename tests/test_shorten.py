# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import pytest

from api.scheduled_deletes import ScheduledDeleteQueue
from .common import token, username
from .common.generators import rand_utf8

pytestmark = pytest.mark.asyncio


async def test_invalid_shorten(test_cli):
    invalid_shit = [f"{username()}" for _ in range(100)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f"/s/{invalid}")
        assert resp.status_code == 404


async def test_shorten(test_cli_user):
    resp = await test_cli_user.post("/api/shorten", json={"url": "https://elixi.re"})

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)
    assert isinstance(data["url"], str)


async def test_shorten_complete(test_cli_user):
    url = "https://elixi.re"
    resp = await test_cli_user.post("/api/shorten", json={"url": url})

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)
    assert isinstance(data["url"], str)

    shorten_url = Path(data["url"])
    domain = shorten_url.parts[1]
    shorten = shorten_url.parts[-1]

    resp = await test_cli_user.get("/api/shortens")
    assert resp.status_code == 200
    rjson = await resp.json

    try:
        shorten_data = next(
            filter(
                lambda shorten_data: shorten_data["shortname"] == shorten,
                rjson["shortens"],
            )
        )
    except StopIteration:
        raise AssertionError("shorten not found")

    assert shorten_data["redirto"] == url
    resp = await test_cli_user.get(f"/s/{shorten}", headers={"host": domain})
    assert resp.status_code == 302
    assert resp.headers["location"] == url

    resp = await test_cli_user.get(f"/s/{shorten}", headers={"host": "undefined.com"})
    assert resp.status_code == 404


async def test_shorten_wrong_scheme(test_cli_user):
    # random invalid schemes
    some_schemes = ("ftp://", "mailto:", "laksjdkj::", token())

    # bad idea but whatever
    wrong = []
    for scheme in some_schemes:
        # random components
        c1 = rand_utf8(15)
        c2 = rand_utf8(15)
        c3 = rand_utf8(15)
        wrong.append(f"{scheme}{c1}.{c2}/{c3}")

    for wrong_url in wrong:
        resp = await test_cli_user.post("/api/shorten", json={"url": wrong_url})
        assert resp.status_code == 400


async def test_shorten_quota(test_cli_user):
    try:
        await test_cli_user.app.db.execute(
            "UPDATE limits SET shlimit = 0 WHERE user_id = $1",
            test_cli_user.user["user_id"],
        )

        resp = await test_cli_user.post(
            "/api/shorten", json={"url": "https://elixi.re"}
        )
        assert resp.status_code == 469
    finally:
        await test_cli_user.app.db.execute(
            "UPDATE limits SET shlimit = DEFAULT WHERE user_id = $1",
            test_cli_user.user["user_id"],
        )


async def test_shorten_scheduled_delete(test_cli_user):
    url = "https://elixi.re"
    resp = await test_cli_user.post(
        "/api/shorten", json={"url": url}, query_string={"retention_time": "PT3S"}
    )

    assert resp.status_code == 200
    data = await resp.json
    shorten_url = Path(data["url"])
    domain = shorten_url.parts[1]
    shorten = shorten_url.parts[-1]

    resp = await test_cli_user.get(f"/s/{shorten}", headers={"host": domain})
    assert resp.status_code == 302
    assert resp.headers["location"] == url

    job_id = data.get("scheduled_delete_job_id")
    assert job_id is not None
    status = await ScheduledDeleteQueue.fetch_job_status(job_id)
    assert status is not None

    await ScheduledDeleteQueue.wait_job(job_id)

    resp = await test_cli_user.get(f"/s/{shorten}", headers={"host": domain})
    assert resp.status_code == 404
