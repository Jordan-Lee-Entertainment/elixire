# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from .common import hexs

from api.common.domain import create_domain, delete_domain

pytestmark = pytest.mark.asyncio


async def test_domains_common_functions(test_cli_admin):
    name = f"domain-{hexs(10)}.tld"

    # create a domain
    async with test_cli_admin.app.app_context():
        domain_id = await create_domain(name, owner_id=test_cli_admin.user["user_id"])

    # test that it exists with the correct info
    row = await test_cli_admin.app.db.fetchrow(
        """
        SELECT domain, admin_only, official, permissions
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    assert row is not None
    assert row["domain"] == name
    assert row["admin_only"] is False
    assert row["official"] is False
    assert row["permissions"] == 3

    # test that the permission mapping exists
    row = await test_cli_admin.app.db.fetchrow(
        """
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """,
        domain_id,
    )

    assert row is not None
    assert row["user_id"] == test_cli_admin.user["user_id"]

    # delete the domain
    async with test_cli_admin.app.app_context():
        results = await delete_domain(domain_id)

    assert isinstance(results, dict)
    assert results["result"] == "DELETE 1"
    assert results["file_move_result"] == "UPDATE 0"
    assert results["shorten_move_result"] == "UPDATE 0"
    assert results["users_move_result"] == "UPDATE 0"
    assert results["users_shorten_move_result"] == "UPDATE 0"

    # test that the permission mapping no longer exists
    row = await test_cli_admin.app.db.fetchrow(
        """
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """,
        domain_id,
    )

    assert row is None


async def assert_domains(resp):
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["domains"], dict)


async def test_domains_nouser(test_cli):
    resp = await test_cli.get("/api/domains")
    await assert_domains(resp)


async def test_domains_user(test_cli_user):
    resp = await test_cli_user.get("/api/domains")
    await assert_domains(resp)


async def test_domains_admin(test_cli_admin):
    resp = await test_cli_admin.get("/api/domains")
    await assert_domains(resp)
