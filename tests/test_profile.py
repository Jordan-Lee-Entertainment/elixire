# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .common import token, username, email

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

    # dict checking is over the test_limits_work function
    assert isinstance(rjson["limits"], dict)

    # test_stats already checks data
    assert isinstance(rjson["stats"], dict)

    dstatus = rjson["dump_status"]
    assert isinstance(dstatus, dict)
    assert isinstance(dstatus["state"], str)


async def test_limits_work(test_cli_user):
    resp = await test_cli_user.get("/api/limits")

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    assert isinstance(rjson["limit"], int)
    assert isinstance(rjson["used"], int)
    assert rjson["used"] <= rjson["limit"]

    assert isinstance(rjson["shortenlimit"], int)
    assert isinstance(rjson["shortenused"], int)
    assert rjson["shortenused"] <= rjson["shortenlimit"]


async def test_patch_profile(test_cli_user):
    # request 1: getting profile info to
    # change back to later
    profileresp = await test_cli_user.get("/api/profile")

    assert profileresp.status_code == 200
    profile = await profileresp.json
    assert isinstance(profile, dict)

    # request 2: updating profile
    new_uname = username()

    resp = await test_cli_user.patch(
        "/api/profile",
        json={
            "username": f"test{new_uname}",
            "email": email(),
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
    assert isinstance(rjson["updated_fields"], list)

    # check if api acknowledged our updates
    assert "username" in rjson["updated_fields"]
    assert "email" in rjson["updated_fields"]
    assert "paranoid" in rjson["updated_fields"]

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
    assert isinstance(rjson["updated_fields"], list)

    assert "username" in rjson["updated_fields"]
    assert "email" in rjson["updated_fields"]
    assert "paranoid" in rjson["updated_fields"]


async def test_profile_wrong_token(test_cli):
    """Test the profile route with wrong tokens."""
    resp = await test_cli.get("/api/profile", headers={"Authorization": token()})
    assert resp.status_code == 403
