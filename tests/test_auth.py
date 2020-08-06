# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .common import token, username, email, extract_first_url
from api.models import User

pytestmark = pytest.mark.asyncio


async def test_login(test_cli_user):
    resp = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={"user": test_cli_user["username"], "password": test_cli_user["password"]},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["token"], str)


async def test_apikey(test_cli_user):
    resp = await test_cli_user.post(
        "/api/auth/apikey",
        do_token=False,
        json={"user": test_cli_user["username"], "password": test_cli_user["password"]},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["api_key"], str)
    assert rjson["api_key"].startswith("u")


async def test_login_badinput(test_cli_user):
    resp = await test_cli_user.post(
        "/api/auth/login", do_token=False, json={"user": test_cli_user["username"]}
    )

    assert resp.status_code == 400


async def test_login_badpwd(test_cli_user):
    response = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={"user": test_cli_user["username"], "password": token()},
    )

    assert response.status_code == 403


async def test_login_baduser(test_cli_user):
    resp = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={"user": username(), "password": test_cli_user["password"]},
    )

    assert resp.status_code == 403


async def test_no_token(test_cli):
    """Test no token request."""
    resp = await test_cli.get("/api/profile")
    assert resp.status_code == 403


async def test_invalid_token(test_cli):
    """Test invalid token."""
    resp = await test_cli.get("/api/profile", headers={"Authorization": token()})
    assert resp.status_code == 403


async def test_valid_token(test_cli_user):
    resp = await test_cli_user.get("/api/profile")
    assert resp.status_code == 200


async def test_revoke(test_cli_user):
    resp = await test_cli_user.get("/api/profile")
    assert resp.status_code == 200

    resp = await test_cli_user.post(
        "/api/auth/revoke",
        do_token=False,
        json={"user": test_cli_user["username"], "password": test_cli_user["password"]},
    )

    assert resp.status_code == 204

    resp = await test_cli_user.get("/api/profile")
    assert resp.status_code == 403


async def test_login_deactivated(test_cli_user):
    """Test logging in with a deactivated user."""
    await test_cli_user.app.db.execute(
        """
        UPDATE users
        SET active = false
        WHERE user_id = $1
        """,
        test_cli_user["user_id"],
    )

    resp = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={"user": test_cli_user["username"], "password": test_cli_user["password"]},
    )

    assert resp.status_code == 403


async def test_username_recovery(test_cli_user):
    """Test username recovery"""
    resp = await test_cli_user.post(
        "/api/auth/recover_username",
        do_token=False,
        json={"email": test_cli_user.user["email"]},
    )
    assert resp.status_code == 204

    email_data = test_cli_user.app._email_list[-1]
    assert test_cli_user.user["username"] in email_data["content"]


async def test_password_reset(test_cli_user):
    """Test password recovery logic"""
    resp = await test_cli_user.post(
        "/api/profile/reset_password",
        do_token=False,
        json={"name": test_cli_user.user["username"]},
    )
    assert resp.status_code == 204

    email_data = test_cli_user.app._email_list[-1]
    password_url = extract_first_url(email_data["content"])
    email_token = password_url.fragment

    new_password = username()
    resp = await test_cli_user.post(
        "/api/profile/reset_password_confirm",
        do_token=False,
        json={"token": email_token, "new_password": new_password},
    )

    assert resp.status_code == 204

    resp = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={
            "user": test_cli_user.user["username"],
            "password": test_cli_user.user["password"],
        },
    )

    assert resp.status_code == 403

    resp = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={"user": test_cli_user.user["username"], "password": new_password},
    )

    assert resp.status_code == 200


async def test_register(test_client):
    """Test the registration of a user"""
    user_name = username()
    user_pass = username()

    resp = await test_client.post(
        "/api/auth/register",
        json={
            "name": user_name,
            "password": user_pass,
            "email": email(),
            "discord_user": "asd#1234",
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["user_id"], str)

    async with test_client.app.app_context():
        user = await User.fetch(int(rjson["user_id"]))

    assert user is not None
    test_client.add_resource(user)

    assert isinstance(rjson["require_approvals"], bool)
    assert (
        rjson["require_approvals"] == test_client.app.econfig.REQUIRE_ACCOUNT_APPROVALS
    )

    await test_client.app.db.execute(
        "update users set active = true where user_id = $1", user.id
    )

    resp = await test_client.post(
        "/api/auth/login", json={"user": user_name, "password": user_pass},
    )
    assert resp.status_code == 200

    assert test_client.app._email_list
    assert test_client.app._webhook_list
