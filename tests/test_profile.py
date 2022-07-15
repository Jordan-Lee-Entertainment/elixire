# elixire: Image Host software
# Copyright 2018-2022, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .common import token, username, email
from .test_upload import png_request
from .util.helpers import extract_url_from_emails

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
            # change to a random username
            "username": f"elixire-test-profile-update-{new_uname}",
            # random email
            "email": email(),
            # users dont have paranoid by default, so
            # change that too. the more we change,
            # the better
            "paranoid": True,
            "password": test_cli_user.password,
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
            "username": test_cli_user.username,
            "email": test_cli_user.email,
            "paranoid": False,
            "password": test_cli_user.password,
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert isinstance(rjson["updated_fields"], list)

    # making sure...
    assert "username" in rjson["updated_fields"]
    assert "email" in rjson["updated_fields"]
    assert "paranoid" in rjson["updated_fields"]


async def test_profile_wrong_token(test_cli):
    """Test the profile route with wrong token."""
    resp = await test_cli.get("/api/profile", headers={"Authorization": token()})
    assert resp.status_code == 403


async def test_user_deletion(test_cli_quick_user):
    # setup:
    # - create file
    # - create shorten
    app = test_cli_quick_user.app

    kwargs = png_request()
    resp = await test_cli_quick_user.post("/api/upload", **kwargs)

    assert resp.status_code == 200
    respjson = await resp.json
    file_shortname = respjson["shortname"]

    # act: delete account

    old_email_count = len(app._test_email_list)
    resp = await test_cli_quick_user.delete(
        "/api/account", json={"password": test_cli_quick_user.password}
    )
    assert resp.status_code == 200

    deletion_url = await extract_url_from_emails(
        test_cli_quick_user.app, old_email_count
    )

    resp = await test_cli_quick_user.post(
        "/api/delete_confirm",
        query_string={"url": deletion_url.fragment},
    )
    assert resp.status_code == 200

    # verify
    # - cant call profile anymore
    # - file should still exist in files table
    # - shorten should still exist in shortens table

    resp = await test_cli_quick_user.get("/api/profile")
    assert resp.status_code == 403

    row = await app.db.fetchrow(
        "SELECT deleted FROM files WHERE filename = $1", file_shortname
    )
    assert row is not None
    assert row["deleted"]
