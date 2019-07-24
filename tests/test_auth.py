# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from .creds import USERNAME, PASSWORD
from .common import token, username, login_normal, login_admin
from .test_admin import _extract_uid


async def test_login(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': USERNAME,
        'password': PASSWORD,
    })

    assert response.status == 200
    resp_json = await response.json()
    assert isinstance(resp_json, dict)
    assert isinstance(resp_json['token'], str)


async def test_login_deactivated(test_cli):
    # login using the hi user
    hi_token = await login_normal(test_cli)
    user_id = _extract_uid(hi_token)

    # login admin to deactivate the account
    admin_token = await login_admin(test_cli)

    resp = await test_cli.post(f'/api/admin/deactivate/{user_id}', headers={
        'Authorization': admin_token,
    })

    assert resp.status == 200

    # "user is deactivated" when correct password provided
    resp = await test_cli.post('/api/login', json={
        'user': USERNAME,
        'password': PASSWORD,
    })

    assert resp.status == 403
    json = await resp.json()
    assert json['message'] == 'User is deactivated'

    # "user or password invalid" when incorrect password provided
    resp = await test_cli.post('/api/login', json={
        'user': USERNAME,
        'password': 'notthepassword',
    })

    assert resp.status == 403
    json = await resp.json()
    assert json['message'] == 'User or password invalid'

    # reactivate user
    resp = await test_cli.post(f'/api/admin/activate/{user_id}', headers={
        'Authorization': admin_token,
    })

    assert resp.status == 200


async def test_login_badinput(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': USERNAME,
    })

    assert response.status == 400


async def test_login_badpwd(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': USERNAME,
        'password': token(),
    })

    assert response.status == 403


async def test_login_baduser(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': username(),
        'password': PASSWORD,
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
        'user': USERNAME,
        'password': PASSWORD
    })

    assert revoke_call.status == 200

    response_invalid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_invalid.status == 403
