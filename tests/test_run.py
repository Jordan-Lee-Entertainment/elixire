# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

pytestmark = pytest.mark.asyncio


async def test_api(test_cli):
    response = await test_cli.get("/api/hello")
    assert response.status_code == 200
    resp_json = await response.json
    assert isinstance(resp_json["name"], str)
    assert isinstance(resp_json["version"], str)


async def test_api_features(test_cli):
    resp = await test_cli.get("/api/features")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson["uploads"], bool)
    assert isinstance(rjson["shortens"], bool)
    assert isinstance(rjson["registrations"], bool)
    assert isinstance(rjson["pfupdate"], bool)


async def test_wpadmin(test_cli):
    resp = await test_cli.get("/wp-login.php")
    assert resp.status_code == 302
