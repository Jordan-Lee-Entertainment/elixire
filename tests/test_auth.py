# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .common import token, username, email, login_admin
from api.bp.profile import delete_user

pytestmark = pytest.mark.asyncio


async def test_login(test_cli_user):
    response = await test_cli_user.post(
        "/api/login",
        do_token=False,
        json={
            "user": test_cli_user.username,
            "password": test_cli_user.password,
        },
    )

    assert response.status_code == 200
    resp_json = await response.json
    assert isinstance(resp_json, dict)
    assert isinstance(resp_json["token"], str)


async def test_login_deactivated(test_cli, test_cli_user):
    # login using the hi user
    user_id = test_cli_user.id

    # login admin to deactivate the account
    admin_token = await login_admin(test_cli)
    resp = await test_cli.post(
        f"/api/admin/deactivate/{user_id}",
        headers={
            "Authorization": admin_token,
        },
    )
    test_cli_user.must_reset()

    assert resp.status_code == 200

    # "user is deactivated" when correct password provided
    resp = await test_cli.post(
        "/api/login",
        json={
            "user": test_cli_user.username,
            "password": test_cli_user.password,
        },
    )

    assert resp.status_code == 403
    json = await resp.json
    assert json["message"] == "User is deactivated"

    # "user or password invalid" when incorrect password provided
    resp = await test_cli.post(
        "/api/login",
        json={
            "user": test_cli_user.username,
            "password": "notthepassword",
        },
    )

    assert resp.status_code == 403
    json = await resp.json
    assert json["message"] == "User or password invalid"


async def test_login_badinput(test_cli_user):
    response = await test_cli_user.post(
        "/api/login",
        do_token=False,
        json={
            "user": test_cli_user.username,
        },
    )

    assert response.status_code == 400

    response = await test_cli_user.post(
        "/api/login",
        do_token=False,
        json={
            "user": test_cli_user.username,
            "password": token(),
        },
    )

    assert response.status_code == 403

    response = await test_cli_user.post(
        "/api/login",
        do_token=False,
        json={
            "user": username(),
            "password": test_cli_user.password,
        },
    )

    assert response.status_code == 403


async def test_no_token(test_cli):
    """Test no token request."""
    response = await test_cli.get("/api/profile", headers={})
    assert response.status_code == 403


async def test_invalid_token(test_cli):
    """Test invalid token."""
    response = await test_cli.get(
        "/api/profile",
        headers={"Authorization": token()},
    )
    assert response.status_code == 403


async def test_valid_token(test_cli_user):
    resp = await test_cli_user.get("/api/profile")
    assert resp.status_code == 200


async def test_revoke(test_cli_user):
    revoke_call = await test_cli_user.post(
        "/api/revoke",
        json={
            "user": test_cli_user.username,
            "password": test_cli_user.password,
        },
    )
    test_cli_user.must_reset()

    assert revoke_call.status_code == 200

    response_invalid = await test_cli_user.get("/api/profile")
    assert response_invalid.status_code == 403


async def test_register(test_cli):
    """Test the registration of a user"""
    user_name = username()
    user_pass = username() * 2

    resp = await test_cli.post(
        "/api/register",
        json={
            "username": user_name,
            "password": user_pass,
            "email": email(),
            "discord_user": "asd#1234",
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["user_id"], str)

    user_id = int(rjson["user_id"])
    try:
        await test_cli.app.db.execute(
            "update users set active = true where user_id = $1", user_id
        )

        resp = await test_cli.post(
            "/api/login",
            json={
                "user": user_name,
                "password": user_pass,
            },
        )
        assert resp.status_code == 200

        # TODO email/webhook testing
        # assert test_cli.app._email_list
        # assert test_cli.app._webhook_list
    finally:
        async with test_cli.app.app_context():
            await delete_user(user_id)
