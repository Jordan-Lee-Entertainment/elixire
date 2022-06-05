# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from pathlib import Path
from .common import token, username, login_admin

pytestmark = pytest.mark.asyncio


async def test_invalid_shorten(test_cli):
    invalid_shit = [f"{username()}" for _ in range(10)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f"/s/{invalid}")
        assert resp.status_code == 404


async def test_shorten(test_cli, test_cli_user):
    resp = await test_cli_user.post(
        "/api/shorten",
        json={"url": "https://elixi.re"},
    )

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)
    assert isinstance(data["url"], str)
    shortname = data["shortname"]

    atoken = await login_admin(test_cli)
    resp = await test_cli.get(
        f"/api/admin/shorten/{shortname}",
        headers={"authorization": atoken},
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert rjson["filename"] == shortname


async def test_shorten_complete(test_cli, test_cli_user):
    url = "https://elixi.re"

    resp = await test_cli_user.post(
        "/api/shorten",
        json={
            "url": url,
        },
    )

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)
    assert isinstance(data["url"], str)

    shorten_url = Path(data["url"])
    domain = shorten_url.parts[1]
    shortname = shorten_url.parts[-1]

    listdata = await test_cli_user.get("/api/list?page=0")
    assert listdata.status_code == 200

    listdata = await listdata.json

    shorten_data = listdata["shortens"][shortname]
    assert shorten_data["redirto"] == url

    resp = await test_cli.get(f"/s/{shortname}", headers={"host": domain})
    assert resp.status_code == 302
    assert resp.headers["location"] == url

    resp = await test_cli.get(f"/s/{shortname}", headers={"host": "undefined.com"})
    assert resp.status_code == 404


async def test_shorten_wrong_scheme(test_cli_user):
    some_schemes = [
        "ftp://",
        "mailto:",
        "laksjdkj::",
        token(),
    ]

    # bad idea but whatever
    wrong = []
    for scheme in some_schemes:
        wrong += [f"{scheme}{token()}.{token()}" for _ in range(10)]

    for wrong_url in wrong:
        resp = await test_cli_user.post(
            "/api/shorten",
            json={
                "url": wrong_url,
            },
        )

        assert resp.status_code == 400
