# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .common import login_admin

pytestmark = pytest.mark.asyncio


async def assert_domains(resp):
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["domains"], dict)


async def test_domains_nouser(test_cli):
    resp = await test_cli.get("/api/domains")
    await assert_domains(resp)


async def test_domains_user(test_cli_user):
    resp = await test_cli_user.get("/api/domains")
    await assert_domains(resp)


async def test_domains_admin(test_cli):
    atoken = await login_admin(test_cli)
    resp = await test_cli.get(
        "/api/domains",
        headers={
            "Authorization": atoken,
        },
    )
    await assert_domains(resp)
