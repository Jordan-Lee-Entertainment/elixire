# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from api.models import Domain, User
from tests.common.generators import username

pytestmark = pytest.mark.asyncio


async def test_user_model(test_cli_user):
    async with test_cli_user.app.app_context():
        user = await User.fetch(test_cli_user["user_id"])
        assert user is not None
        assert user.id == test_cli_user["user_id"]

        user = await User.fetch_by(username=username())
        assert user is None


async def test_domain_model(test_cli_user):
    domain = await test_cli_user.create_domain()
    async with test_cli_user.app.app_context():
        fetched_domain = await Domain.fetch(domain.id)
        assert fetched_domain is not None
        assert fetched_domain.id == domain.id
