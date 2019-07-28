# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .creds import USERNAME, PASSWORD
from .common import token, username, login_normal


@pytest.mark.asyncio
async def test_login(test_cli):
    response = await test_cli.post(
        "/api/login", json={"user": USERNAME, "password": PASSWORD}
    )

    assert response.status_code == 200
    resp_json = await response.json
    assert isinstance(resp_json, dict)
    assert isinstance(resp_json["token"], str)


@pytest.mark.asyncio
async def test_login_badinput(test_cli):
    response = await test_cli.post("/api/login", json={"user": USERNAME})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_badpwd(test_cli):
    response = await test_cli.post(
        "/api/login", json={"user": USERNAME, "password": token()}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_login_baduser(test_cli):
    response = await test_cli.post(
        "/api/login", json={"user": username(), "password": PASSWORD}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_no_token(test_cli):
    """Test no token request."""
    response = await test_cli.get("/api/profile", headers={})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_invalid_token(test_cli):
    """Test invalid token."""
    response = await test_cli.get("/api/profile", headers={"Authorization": token()})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_valid_token(test_cli):
    token = await login_normal(test_cli)
    response_valid = await test_cli.get(
        "/api/profile", headers={"Authorization": token}
    )

    assert response_valid.status_code == 200


@pytest.mark.asyncio
async def test_revoke(test_cli):
    token = await login_normal(test_cli)

    resp = await test_cli.get("/api/profile", headers={"Authorization": token})

    assert resp.status_code == 200

    resp = await test_cli.post(
        "/api/revoke", json={"user": USERNAME, "password": PASSWORD}
    )

    assert resp.status_code == 204

    resp = await test_cli.get("/api/profile", headers={"Authorization": token})

    assert resp.status_code == 403
