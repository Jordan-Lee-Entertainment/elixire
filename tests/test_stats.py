# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

pytestmark = pytest.mark.asyncio


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
    assert isinstance(info["tags"], list)

    pub = rjson["0"]["stats"]
    assert isinstance(pub["users"], int)
    assert isinstance(pub["files"], int)
    assert isinstance(pub["shortens"], int)
