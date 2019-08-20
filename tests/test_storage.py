# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import secrets

pytestmark = pytest.mark.asyncio


async def test_basic_storage_operations(app):
    key = secrets.token_hex(8)
    value = secrets.token_hex(8)

    try:
        upstream_value = await app.storage.get(key)
        assert not upstream_value

        await app.storage.set(key, value)

        upstream_value = await app.storage.get(key)
        assert upstream_value
        assert upstream_value.value == value
    finally:
        await app.storage.raw_invalidate(key)


async def test_user_storage(test_cli_user):
    app = test_cli_user.app

    assert (await app.storage.get_username(test_cli_user["user_id"])) == test_cli_user[
        "username"
    ]

    assert (await app.storage.get_uid(test_cli_user["username"])) == test_cli_user[
        "user_id"
    ]


async def test_domain_storage(test_domain, app):
    # TODO maybe copy test_domain.name and replace by a
    # subdomain, then compare it to get_domain_id(..)[1]
    assert (await app.storage.get_domain_id(test_domain.name))[0] == test_domain.id