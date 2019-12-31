# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

pytestmark = pytest.mark.asyncio


def _extract_uid(token: str) -> str:
    split = token.split(".")
    try:
        uid, _ = split
    except ValueError:
        uid, _, _, = split

    return uid


async def test_non_admin(test_cli_user):
    resp = await test_cli_user.get("/api/admin/test")
    assert resp.status_code != 200
    assert resp.status_code == 403


async def test_admin(test_cli_admin):
    resp = await test_cli_admin.get("/api/admin/test")
    assert resp.status_code == 200
    data = await resp.json

    assert isinstance(data, dict)
    assert data["admin"]


async def test_user_fetch(test_cli_admin):
    uid = test_cli_admin["user_id"]
    resp = await test_cli_admin.get(f"/api/admin/users/{uid}")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert isinstance(rjson["id"], str)
    assert isinstance(rjson["name"], str)
    assert isinstance(rjson["active"], bool)
    assert isinstance(rjson["admin"], bool)
    assert isinstance(rjson["domain"], int)
    assert isinstance(rjson["subdomain"], str)
    assert isinstance(rjson["consented"], bool) or rjson["consented"] is None
    assert isinstance(rjson["email"], str)
    assert isinstance(rjson["paranoid"], bool)
    assert isinstance(rjson["limits"], dict)

    # trying to fetch the user from the username we got
    # should also work
    user_id = rjson["id"]
    resp = await test_cli_admin.get(f'/api/admin/users/by-username/{rjson["name"]}')

    assert resp.status_code == 200
    rjson = await resp.json

    # just checking the id should work, as the response of
    # /by-username/ is the same as doing it by ID.
    assert isinstance(rjson["id"], str)
    assert rjson["id"] == user_id


async def test_user_activate_cycle(test_cli_user, test_cli_admin):
    """
    logic here is to:
     - deactivate user
     - check the user's profile, make sure its deactivated
     - activate user
     - check profile again, making sure its activated
    """
    uid = test_cli_user.user["user_id"]

    # deactivate
    resp = await test_cli_admin.post(f"/api/admin/users/deactivate/{uid}")
    assert resp.status_code == 204

    # check profile for deactivation
    resp = await test_cli_admin.get(f"/api/admin/users/{uid}")

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert not rjson["active"]

    # activate
    resp = await test_cli_admin.post(f"/api/admin/users/activate/{uid}")
    assert resp.status_code == 204

    # check profile
    resp = await test_cli_admin.get(f"/api/admin/users/{uid}")

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert rjson["active"]


async def test_user_search(test_cli_admin):
    """Test seaching of users."""
    # there isnt much other testing than calling the route
    # and checking for the data types...

    # NOTE no idea how we would test all the query arguments
    # in the route.
    resp = await test_cli_admin.get("/api/admin/users/search")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert isinstance(rjson["results"], list)

    pag = rjson["pagination"]
    assert isinstance(pag, dict)
    assert isinstance(pag["total"], int)
    assert isinstance(pag["current"], int)


async def test_domain_search(test_cli_admin):
    def assert_standard_response(json):
        assert isinstance(json, dict)
        assert isinstance(json["results"], dict)

        pag = json["pagination"]
        assert isinstance(pag, dict)
        assert isinstance(pag["total"], int)
        assert isinstance(pag["current"], int)

    # no query -- returns all users, paginated
    resp = await test_cli_admin.get("/api/admin/domains/search")

    assert resp.status_code == 200

    json = await resp.json
    assert_standard_response(json)

    # sample query
    resp = await test_cli_admin.get(
        "/api/admin/domains/search", query_string={"query": "elix"}
    )

    assert resp.status_code == 200

    json = await resp.json
    assert_standard_response(json)

    assert all(
        "elix" in domain["info"]["domain"] for domain in json["results"].values()
    )


async def test_domain_stats(test_cli_admin):
    """Get instance-wide domain stats."""
    resp = await test_cli_admin.get("/api/admin/domains")

    assert resp.status_code == 200
    rjson = await resp.json

    # not the best data validation...
    assert isinstance(rjson, dict)
    for domain in rjson.values():
        assert isinstance(domain, dict)
        assert isinstance(domain["info"], dict)
        assert isinstance(domain["info"]["tags"], list)
        assert isinstance(domain["stats"], dict)
        assert isinstance(domain["public_stats"], dict)


async def test_domain_get(test_cli_admin):
    resp = await test_cli_admin.get("/api/admin/domains/38918583")
    assert resp.status_code == 404


async def test_domain_patch(test_cli_user, test_cli_admin):
    """Test editing of a single domain."""
    user_id = str(test_cli_user.user["user_id"])
    admin_id = str(test_cli_admin.user["user_id"])

    # we can always assume tags 1 and 2 will exist (admin_only and official)
    # so we can use those

    resp = await test_cli_admin.patch(
        "/api/admin/domains/0",
        json={"owner_id": user_id, "permissions": 0, "tags": [1, 2]},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    fields = rjson["updated"]
    assert isinstance(fields, list)
    assert "owner_id" in fields
    assert "permissions" in fields
    assert "tags" in fields

    # fetch domain info
    resp = await test_cli_admin.get("/api/admin/domains/0")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    dinfo = rjson["info"]
    assert isinstance(dinfo, dict)
    if dinfo.get("owner"):
        assert dinfo["owner"]["id"] == user_id
    assert dinfo["permissions"] == 0
    assert [tag["id"] for tag in dinfo["tags"]] == [1, 2]

    # reset the domain properties
    # to sane defaults
    resp = await test_cli_admin.patch(
        "/api/admin/domains/0",
        json={"owner_id": admin_id, "permissions": 3, "tags": []},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    fields = rjson["updated"]
    assert isinstance(fields, list)
    assert "owner_id" in fields
    assert "permissions" in fields
    assert "tags" in fields

    # fetch domain info, again, to make sure.
    resp = await test_cli_admin.get("/api/admin/domains/0")

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    dinfo = rjson["info"]
    assert isinstance(dinfo, dict)
    if dinfo.get("owner"):
        assert dinfo["owner"]["id"] == admin_id
    assert dinfo["permissions"] == 3
    assert not dinfo["tags"]


async def test_user_patch(test_cli_user, test_cli_admin):
    user_id = test_cli_user.user["user_id"]

    # request 1: change default user to admin, etc
    resp = await test_cli_admin.patch(
        f"/api/admin/users/{user_id}",
        json={"upload_limit": 1000, "shorten_limit": 1000},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, list)
    assert "upload_limit" in rjson
    assert "shorten_limit" in rjson

    # request 2: check by getting user info
    # TODO maybe we can check GET /api/profile
    resp = await test_cli_admin.get(f"/api/admin/users/{user_id}")

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["limits"], dict)
    assert rjson["limits"]["file_byte_limit"] == 1000
    assert rjson["limits"]["shorten_limit"] == 1000

    # request 3: changing it back
    resp = await test_cli_admin.patch(
        f"/api/admin/users/{user_id}",
        json={"upload_limit": 104_857_600, "shorten_limit": 100},
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, list)
    assert "upload_limit" in rjson
    assert "shorten_limit" in rjson

    # TODO check the set values here


async def test_my_stats_as_admin(test_cli_admin):
    """Test the personal domain stats route but as an admin."""
    resp = await test_cli_admin.get("/api/stats/my_domains")
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)

    try:
        domain_id = next(iter(rjson.keys()))
    except StopIteration:
        # we can't test if the admin user doesn't own any domains
        # and that is a possible case of the environment.
        return

    dom = rjson[domain_id]

    info = dom["info"]
    assert isinstance(info["domain"], str)
    assert isinstance(info["permissions"], int)
    assert isinstance(info["tags"], list)

    stats = dom["stats"]
    assert isinstance(stats["users"], int)
    assert isinstance(stats["files"], int)
    assert isinstance(stats["size"], int)
    assert isinstance(stats["shortens"], int)


async def test_domain_tag_create_delete(test_cli_admin):
    """Test the personal domain stats route but as an admin."""
    resp = await test_cli_admin.put(
        "/api/admin/domains/tag", json={"label": "admin_only"}
    )
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["id"], int)
    tag_id = rjson["id"]

    try:
        resp = await test_cli_admin.get("/api/admin/domains/tags")
        assert resp.status_code == 200
        rjson = await resp.json
        assert isinstance(rjson, dict)
        assert isinstance(rjson["tags"], list)
        assert any(tag["id"] == tag_id for tag in rjson["tags"])

        resp = await test_cli_admin.patch(
            f"/api/admin/domains/tag/{tag_id}", json={"label": "asdf"}
        )
        assert resp.status_code == 200
        rjson = await resp.json
        assert isinstance(rjson, dict)
        assert rjson["id"] == tag_id
        assert rjson["label"] == "asdf"
    finally:
        resp = await test_cli_admin.delete(f"/api/admin/domains/tag/{tag_id}")
        assert resp.status_code == 204
