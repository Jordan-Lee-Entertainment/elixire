# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

pytestmark = pytest.mark.asyncio


async def test_stats(test_cli_user):
    resp = await test_cli_user.get("/api/stats")

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    assert isinstance(rjson["total_files"], int)
    assert isinstance(rjson["total_deleted_files"], int)
    assert isinstance(rjson["total_bytes"], (float, int))
    assert isinstance(rjson["total_shortens"], int)


async def test_domains(test_cli_admin):
    # admins always own at least domain 0
    resp = await test_cli_admin.get("/api/stats/my_domains")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert isinstance(rjson["0"], dict)

    info = rjson["0"]["info"]
    assert isinstance(info["domain"], str)
    assert isinstance(info["permissions"], int)
    assert isinstance(info["cf_enabled"], bool)
    assert isinstance(info["admin_only"], bool)
    assert isinstance(info["official"], bool)

    pub = rjson["0"]["stats"]
    assert isinstance(pub["users"], int)
    assert isinstance(pub["files"], int)
    assert isinstance(pub["shortens"], int)
