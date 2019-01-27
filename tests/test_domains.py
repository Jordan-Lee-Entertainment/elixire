# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from .common import token, username, login_normal, login_admin


async def assert_domains(resp):
    assert resp.status == 200

    rjson = await resp.json()
    assert isinstance(rjson, dict)
    assert isinstance(rjson['domains'], dict)


async def test_domains_nouser(test_cli):
    resp = await test_cli.get('/api/domains')
    await assert_domains(resp)


async def test_domains_user(test_cli):
    utoken = await login_normal(test_cli)
    resp = await test_cli.get('/api/domains', headers={
        'Authorization': utoken,
    })

    await assert_domains(resp)


async def test_domains_admin(test_cli):
    atoken = await login_admin(test_cli)
    resp = await test_cli.get('/api/domains', headers={
        'Authorization': atoken,
    })
    await assert_domains(resp)
