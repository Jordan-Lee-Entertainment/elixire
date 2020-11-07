# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
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

    assert await app.storage.get_uid(secrets.token_hex(64)) is None
    assert await app.storage.get_username(secrets.randbits(32)) is None


async def test_domain_storage(test_cli_user):
    # TODO maybe copy test_domain.domain and replace by a
    # subdomain, then compare it to get_domain_id(..)[1]
    test_domain = await test_cli_user.create_domain()
    storage_id = await test_cli_user.app.storage.get_domain_id(test_domain.domain)
    assert storage_id[0] == test_domain.id
