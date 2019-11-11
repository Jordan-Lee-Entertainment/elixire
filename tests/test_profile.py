# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import asyncio
from .common import token, username, email
from api.common.user import create_user, delete_user

pytestmark = pytest.mark.asyncio


async def test_profile_work(test_cli_user):
    """Test the profile user, just getting data."""
    resp = await test_cli_user.get("/api/profile")

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    assert isinstance(rjson["user_id"], str)
    assert isinstance(rjson["username"], str)
    assert isinstance(rjson["active"], bool)
    assert isinstance(rjson["admin"], bool)

    assert rjson["consented"] in (True, False, None)

    assert isinstance(rjson["subdomain"], str)
    assert isinstance(rjson["domain"], int)

    assert_limits(rjson["limits"])
    assert isinstance(rjson["stats"], dict)

    dstatus = rjson["dump_status"]
    assert isinstance(dstatus, dict)
    assert isinstance(dstatus["state"], str)


def assert_limits(limits: dict):
    assert isinstance(limits, dict)

    assert isinstance(limits["limit"], int)
    assert isinstance(limits["used"], int)
    assert limits["used"] <= limits["limit"]

    assert isinstance(limits["shortenlimit"], int)
    assert isinstance(limits["shortenused"], int)
    assert limits["shortenused"] <= limits["shortenlimit"]


async def test_patch_profile(test_cli_user):
    # request 1: getting profile info to
    # change back to later
    profileresp = await test_cli_user.get("/api/profile")

    assert profileresp.status_code == 200
    profile = await profileresp.json
    assert isinstance(profile, dict)

    # request 2: updating profile
    new_uname = f"test{username()}"
    new_email = email()

    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "username": new_uname,
            "email": new_email,
            # users dont have paranoid by default, so
            # change that too. the more we change,
            # the better
            "paranoid": True,
            # password required to change username and email
            "password": test_cli_user["password"],
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert rjson["username"] == new_uname
    assert rjson["email"] == new_email
    assert rjson["paranoid"]

    # request 3: changing profile info back
    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "username": test_cli_user["username"],
            "email": test_cli_user["email"],
            "paranoid": False,
            # password required to change username and email
            "password": test_cli_user["password"],
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert rjson["username"] == test_cli_user["username"]
    assert rjson["email"] == test_cli_user["email"]
    assert not rjson["paranoid"]


async def test_profile_wrong_token(test_cli):
    """Test the profile route with wrong tokens."""
    resp = await test_cli.get("/api/profile", headers={"Authorization": token()})
    assert resp.status_code == 403


async def test_patch_profile_wrong(test_cli_user):
    random_username = username()
    async with test_cli_user.app.app_context():
        random_user = await create_user(random_username, username(), email())

    try:
        resp = await test_cli_user.patch(
            "/api/profile",
            json={"username": random_username, "password": test_cli_user["password"]},
        )

        assert resp.status_code == 400

        rjson = await resp.json

        assert isinstance(rjson, dict)

        # assert we have errors on there
        assert rjson["username"]
    finally:
        async with test_cli_user.app.app_context():
            task = await delete_user(random_user["user_id"], delete=True)
        await asyncio.shield(task)
