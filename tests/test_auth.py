# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import elixire.tests.creds
from elixire.tests.common import token, username, login_normal


async def test_login(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 200
    resp_json = await response.json()
    assert isinstance(resp_json, dict)
    assert isinstance(resp_json['token'], str)


async def test_login_badinput(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
    })

    assert response.status == 400


async def test_login_badpwd(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
        'password': token(),
    })

    assert response.status == 403


async def test_login_baduser(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': username(),
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 403


async def test_no_token(test_cli):
    """Test no token request."""
    response = await test_cli.get('/api/profile', headers={})
    assert response.status == 403


async def test_invalid_token(test_cli):
    """Test invalid token."""
    response = await test_cli.get('/api/profile', headers={
        'Authorization': token(),
    })
    assert response.status == 403


async def test_valid_token(test_cli):
    token = await login_normal(test_cli)
    response_valid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_valid.status == 200


async def test_revoke(test_cli):
    token = await login_normal(test_cli)

    response_valid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_valid.status == 200

    revoke_call = await test_cli.post('/api/revoke', json={
        'user': elixire.tests.creds.USERNAME,
        'password': elixire.tests.creds.PASSWORD
    })

    assert revoke_call.status == 200

    response_invalid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_invalid.status == 403
