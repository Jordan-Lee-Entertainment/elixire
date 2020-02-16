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
    assert isinstance(rjson["domains"], list)

    # NOTE: this test expects domain 0 to be linked to admin ownership

    domain = rjson["domains"][0]
    assert isinstance(domain["id"], int)
    assert isinstance(domain["domain"], str)
    assert isinstance(domain["permissions"], int)
    assert isinstance(domain["tags"], list)

    pub = domain["stats"]
    assert isinstance(pub["user_count"], int)
    assert isinstance(pub["shorten_count"], int)

    assert isinstance(pub["files"], dict)
    assert isinstance(pub["files"]["count"], int)
    assert isinstance(pub["files"]["total_file_bytes"], int)
