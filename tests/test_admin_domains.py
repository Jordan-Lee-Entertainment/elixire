# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from tests.common.generators import username
from api.models import Domain

pytestmark = pytest.mark.asyncio


async def test_admin_create_domain(test_cli_admin):
    domain_name = f"{username()}.com"

    resp = await test_cli_admin.put(
        "/api/admin/domains",
        json={
            "domain": domain_name,
            "permissions": 3,
            "owner_id": test_cli_admin["user_id"],
        },
    )

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    domain = rjson["domain"]
    assert isinstance(domain, dict)
    assert domain["domain"] == domain_name

    # add created domain as a resource so it's deleted by the end
    # of this test
    async with test_cli_admin.app.app_context():
        domain = await Domain.fetch(domain["id"])
        test_cli_admin.add_resource(domain)
