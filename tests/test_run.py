# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

pytestmark = pytest.mark.asyncio


async def test_hello(test_cli):
    """Test basic route"""
    response = await test_cli.get("/api/hello")
    assert response.status_code == 200
    rjson = await response.json

    assert isinstance(rjson["name"], str)
    assert isinstance(rjson["version"], str)
    assert isinstance(rjson["api"], str)
    assert isinstance(rjson["support_email"], str)
    assert isinstance(rjson["ban_period"], str)
    assert isinstance(rjson["ip_ban_period"], str)
    assert isinstance(rjson["rl_threshold"], int)

    assert isinstance(rjson["accepted_mimes"], list)
    assert isinstance(rjson["features"], list)
