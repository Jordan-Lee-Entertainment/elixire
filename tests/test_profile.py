# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
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

    assert isinstance(rjson["id"], str)
    assert isinstance(rjson["name"], str)
    assert isinstance(rjson["active"], bool)
    assert isinstance(rjson["admin"], bool)

    assert rjson["consented"] in (True, False, None)

    assert isinstance(rjson["subdomain"], str)
    assert isinstance(rjson["domain"], int)

    assert_limits(rjson["limits"])
    assert isinstance(rjson["stats"], dict)
    assert isinstance(rjson["stats"]["total_files"], int)
    assert isinstance(rjson["stats"]["total_deleted_files"], int)
    assert isinstance(rjson["stats"]["total_bytes"], int)
    assert isinstance(rjson["stats"]["total_shortens"], int)

    dstatus = rjson["dump_status"]
    if dstatus is not None:
        assert isinstance(dstatus, dict)
        assert isinstance(dstatus["state"], str)


def assert_limits(limits: dict):
    assert isinstance(limits, dict)

    assert isinstance(limits["file_byte_limit"], int)
    assert isinstance(limits["file_byte_used"], int)
    assert limits["file_byte_used"] <= limits["file_byte_limit"]

    assert isinstance(limits["shorten_limit"], int)
    assert isinstance(limits["shorten_used"], int)
    assert limits["shorten_used"] <= limits["shorten_limit"]


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
    new_domain = await test_cli_user.create_domain()
    new_subdomain = username()
    new_shorten_subdomain = username()

    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "name": new_uname,
            "email": new_email,
            "domain": new_domain.id,
            "subdomain": new_subdomain,
            "shorten_domain": new_domain.id,
            "shorten_subdomain": new_shorten_subdomain,
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
    assert rjson["name"] == new_uname
    assert rjson["email"] == new_email
    assert rjson["paranoid"]
    assert rjson["domain"] == new_domain.id
    assert rjson["subdomain"] == new_subdomain
    assert rjson["shorten_domain"] == new_domain.id
    assert rjson["shorten_subdomain"] == new_shorten_subdomain

    # request 3: changing profile info back
    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "name": test_cli_user["username"],
            "email": test_cli_user["email"],
            "paranoid": False,
            # password required to change username and email
            "password": test_cli_user["password"],
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert rjson["name"] == test_cli_user["username"]
    assert rjson["email"] == test_cli_user["email"]
    assert not rjson["paranoid"]


async def test_patch_profile_new_password(test_cli_user):
    old_password = test_cli_user["password"]
    new_password = username()

    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "new_password": new_password,
            "password": old_password,
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)

    # we need to create another token for this test user
    resp = await test_cli_user.post(
        "/api/auth/login",
        do_token=False,
        json={"user": test_cli_user["username"], "password": new_password},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["token"], str)

    test_cli_user.user["password"] = new_password
    test_cli_user.user["token"] = rjson["token"]

    # assert this new token works
    resp = await test_cli_user.get("/api/profile")
    assert resp.status_code == 200


async def test_patch_profile_wrong_password(test_cli_user):
    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "username": username(),
        },
    )
    assert resp.status_code == 400

    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "name": username(),
            "password": username(),
        },
    )
    assert resp.status_code == 403

    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "new_password": username(),
            "password": username(),
        },
    )

    assert resp.status_code == 403


async def test_profile_wrong_token(test_cli):
    """Test the profile route with wrong tokens."""
    resp = await test_cli.get("/api/profile", headers={"Authorization": token()})
    assert resp.status_code == 403


async def test_profile_bare(test_cli_user):
    """Test the profile route with ?bare=true."""
    resp = await test_cli_user.get("/api/profile", query_string={"bare": "true"})
    assert resp.status_code == 200
    json = await resp.json
    assert json == {
        "id": str(test_cli_user["user_id"]),
        "name": test_cli_user["username"],
    }


async def test_patch_profile_wrong(test_cli_user):
    random_username = username()
    random_email = email()
    async with test_cli_user.app.app_context():
        random_user = await create_user(random_username, username(), random_email)

    try:
        resp = await test_cli_user.patch(
            "/api/profile",
            json={
                "name": random_username,
                "email": random_email,
                "domain": -1,
                "shorten_domain": -1,
                "password": test_cli_user["password"],
            },
        )

        assert resp.status_code == 400

        rjson = await resp.json

        assert isinstance(rjson, dict)

        # assert we have errors on there
        assert rjson["name"]
        assert rjson["email"]
        assert rjson["domain"]
        assert rjson["shorten_domain"]
    finally:
        async with test_cli_user.app.app_context():
            task = await delete_user(random_user["user_id"], delete=True)
        await asyncio.shield(task)
