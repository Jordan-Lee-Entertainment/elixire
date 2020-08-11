# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import random
import asyncio
from uuid import UUID
from typing import List
from urllib.parse import parse_qs

import pytest
from violet import JobQueue

from api.models import Domain, User
from tests.common.generators import username
from tests.common.utils import extract_first_url

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

    assert all("elix" in domain["domain"] for domain in json["results"].values())


async def test_domain_stats(test_cli_admin):
    """Get instance-wide domain stats."""
    resp = await test_cli_admin.get("/api/admin/domains")

    assert resp.status_code == 200
    rjson = await resp.json

    # not the best data validation...
    assert isinstance(rjson, dict)
    for domain in rjson.values():
        assert isinstance(domain, dict)
        assert isinstance(domain["tags"], list)
        assert isinstance(domain["stats"], dict)
        assert isinstance(domain["public_stats"], dict)


async def test_domain_get(test_cli_admin):
    resp = await test_cli_admin.get("/api/admin/domains/38918583")
    assert resp.status_code == 404


async def test_domain_patch(test_cli_user, test_cli_admin):
    """Test editing of a single domain."""
    user_id = str(test_cli_user.user["user_id"])
    admin_id = str(test_cli_admin.user["user_id"])

    # Select a random tag that we can use.
    sample_tag_id = await test_cli_admin.app.db.fetchval(
        """
        SELECT tag_id
        FROM domain_tags
        LIMIT 1
        """
    )

    resp = await test_cli_admin.patch(
        "/api/admin/domains/0",
        json={"owner_id": user_id, "permissions": 0, "tags": [sample_tag_id]},
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
    if rjson.get("owner"):
        assert rjson["owner"]["id"] == user_id
    assert rjson["permissions"] == 0
    assert rjson["tags"][0]["id"] == sample_tag_id

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
    if rjson.get("owner"):
        assert rjson["owner"]["id"] == admin_id
    assert rjson["permissions"] == 3
    assert not rjson["tags"]


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


async def test_domain_tag_create_delete(test_cli_admin):
    """Test the personal domain stats route but as an admin."""
    resp = await test_cli_admin.put(
        "/api/admin/domains/tag", json={"label": "testing_tag"}
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
            f"/api/admin/domains/tag/{tag_id}", json={"label": "testing_tag_2"}
        )
        assert resp.status_code == 200
        rjson = await resp.json
        assert isinstance(rjson, dict)
        assert rjson["id"] == tag_id
        assert rjson["label"] == "testing_tag_2"
    finally:
        resp = await test_cli_admin.delete(f"/api/admin/domains/tag/{tag_id}")
        assert resp.status_code == 204


async def do_list_jobs(test_cli_user, *, before=None, after=None, rest: str = ""):
    before = f"before={before}" if before is not None else ""
    after = f"&after={after}" if after is not None else ""

    resp = await test_cli_user.get(
        f"/api/admin/violet_jobs/{JobTestQueue.name}?{before}{after}{rest}"
    )
    assert resp.status_code == 200
    rjson = await resp.json

    objects = rjson["results"]
    assert isinstance(objects, list)

    ids = [UUID(job["job_id"]) for job in objects]
    return objects, ids


async def test_sensible_uuid():
    val_int = random.randint(0, 1000)
    val = UUID(int=val_int)
    assert UUID(int=val.int + 1).int == val_int + 1


async def _null_handler(_ctx, _i):
    pass


class JobTestQueue(JobQueue):
    name = "__test"
    workers = 5

    args = ("test",)

    @classmethod
    def map_persisted_row(_cls, _row):
        return

    @classmethod
    async def push(cls, i, **kwargs):
        return await cls._sched.raw_push(cls, (i,), **kwargs)

    @classmethod
    async def setup(_, _ctx):
        pass

    @classmethod
    async def handle(_, _ctx):
        pass


async def _create_random_jobs(test_cli, count: int) -> List[str]:
    """Create random violet jobs to fill the table."""

    app = test_cli.app
    await app.db.execute("DROP TABLE IF EXISTS __test")
    await app.db.execute(
        """
        CREATE TABLE IF NOT EXISTS __test (
            job_id uuid primary key,
            name text unique,

            state bigint default 0,
            errors text default '',
            inserted_at timestamp without time zone default (now() at time zone 'utc'),
            scheduled_at timestamp without time zone default (now() at time zone 'utc'),
            taken_at timestamp without time zone default null,
            internal_state jsonb default '{}',

            test bigint
        )
        """
    )
    app.sched.register_job_queue(JobTestQueue)

    job_ids: List[str] = []

    for i in range(count):
        job_id = await JobTestQueue.push(i)
        job_ids.append(job_id)

    return job_ids


async def test_violet_jobs(test_cli_admin):
    await _create_random_jobs(test_cli_admin, 20)
    jobs, ids = await do_list_jobs(test_cli_admin, rest="limit=10")
    assert all(a.int >= b.int for a, b in zip(ids, ids[1:]))

    first_id = ids[0]
    last_id = ids[-1]
    jobs, ids = await do_list_jobs(test_cli_admin, after=first_id.hex, rest="&limit=10")
    assert not jobs

    jobs, ids = await do_list_jobs(
        test_cli_admin, before=UUID(int=first_id.int - 1).hex, rest="&limit=10"
    )
    assert first_id not in ids

    jobs, ids = await do_list_jobs(test_cli_admin, before=last_id.hex, rest="&limit=10")
    assert last_id not in ids

    jobs, ids = await do_list_jobs(test_cli_admin, after=last_id.hex, rest="&limit=10")
    assert last_id not in ids
    assert ids[0] == first_id

    jobs, ids = await do_list_jobs(
        test_cli_admin,
        before=UUID(int=first_id.int - 1).hex,
        after=UUID(int=last_id.int + 1).hex,
        rest="&limit=10",
    )
    assert first_id not in ids
    assert last_id not in ids


@pytest.mark.skip(
    reason="breaks due to request context not being found. dunno if issue in violet, or smth else"
)
async def _disabled_test_broadcast(test_cli_admin):
    body = username()
    subject = username()
    resp = await test_cli_admin.post(
        "/api/admin/broadcast", json={"subject": subject, "body": body}
    )
    assert resp.status_code == 204

    # TODO convert broadcast code into a violet job queue so we can wait_job
    await asyncio.sleep(1)

    email = test_cli_admin.app._email_list[-1]
    assert email["subject"] == subject
    assert body in email["content"]


async def test_domain_create(test_cli_admin):
    domain_name = "{username()}.com"
    resp = await test_cli_admin.put(
        "/api/admin/domains",
        json={"domain": domain_name, "owner_id": test_cli_admin.user["user_id"]},
    )
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["domain"], dict)
    domain = rjson["domain"]
    assert isinstance(domain["id"], int)

    # TODO assert more fields from domain?

    async with test_cli_admin.app.app_context():
        domain = await Domain.fetch(domain["id"])
    assert domain is not None
    test_cli_admin.add_resource(domain)

    assert domain.domain == domain_name
    async with test_cli_admin.app.app_context():
        owner = await domain.fetch_owner()
    assert owner is not None
    assert owner.id == test_cli_admin.user["user_id"]


async def test_activation_email(test_cli, test_cli_admin):
    user = await test_cli_admin.create_user(active=False)
    resp = await test_cli_admin.post(f"/api/admin/users/activate_email/{user.id}")
    assert resp.status_code == 204

    email = test_cli_admin.app._email_list[-1]
    url = extract_first_url(email["content"])
    email_key = parse_qs(url.query)["key"][0]

    async with test_cli.app.app_context():
        user = await User.fetch(user.id)
        assert user is not None
        assert not user.active

    # TODO fix the path
    resp = await test_cli.get(
        "/api/admin/users/api/activate_email", query_string={"key": email_key}
    )
    assert resp.status_code == 200

    async with test_cli.app.app_context():
        user = await User.fetch(user.id)
        assert user is not None
        assert user.active


async def test_doll_user_removal(test_cli_admin):
    resp = await test_cli_admin.delete("/api/admin/users/0")
    assert resp.status_code == 400
