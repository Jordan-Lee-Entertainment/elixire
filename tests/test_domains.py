# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from api.storage import solve_domain
from api.common.domain import create_domain, delete_domain
from api.models import Domain

from .common import hexs

pytestmark = pytest.mark.asyncio


async def test_domains_common_functions(test_cli_admin):
    name = f"domain-{hexs(10)}.tld"

    # create a domain
    async with test_cli_admin.app.app_context():
        domain_id = await create_domain(name, owner_id=test_cli_admin.user["user_id"])

    try:
        # test that it exists with the correct info
        row = await test_cli_admin.app.db.fetchrow(
            """
            SELECT domain, permissions
            FROM domains
            WHERE domain_id = $1
            """,
            domain_id,
        )

        assert row is not None
        assert row["domain"] == name
        assert row["permissions"] == 3

        # test that the owner mapping exists
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

        # assert tags are empty for new domains
        async with test_cli_admin.app.app_context():
            domain = await Domain.fetch(domain_id)
            assert domain is not None

        assert not domain.tags
    finally:
        async with test_cli_admin.app.app_context():
            results = await delete_domain(domain_id)

    assert isinstance(results, dict)
    assert results["result"] == "DELETE 1"
    assert results["file_move_result"] == "UPDATE 0"
    assert results["shorten_move_result"] == "UPDATE 0"
    assert results["users_move_result"] == "UPDATE 0"
    assert results["users_shorten_move_result"] == "UPDATE 0"

    # test that the owner mapping no longer exists
    row = await test_cli_admin.app.db.fetchrow(
        """
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """,
        domain_id,
    )

    assert row is None


async def test_domains_solving():
    possibilities = solve_domain("sample.domain.tld")
    assert len(possibilities) == 3
    assert possibilities == ["*.sample.domain.tld", "sample.domain.tld", "*.domain.tld"]


async def test_domainlist(test_cli):
    resp = await test_cli.get("/api/domains")
    assert resp.status_code == 200

    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert isinstance(rjson["domains"], list)

    for domain in rjson["domains"]:
        assert isinstance(domain, dict)
        assert isinstance(domain["id"], int)
        assert isinstance(domain["domain"], str)
        assert isinstance(domain["tags"], list)

        for tag in domain["tags"]:
            assert isinstance(tag, dict)
            assert isinstance(tag["id"], int)
            assert isinstance(tag["label"], str)
