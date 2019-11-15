# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import random
import secrets
import pytest

from api.common.user import delete_user
from .common import username, email, hexs

pytestmark = pytest.mark.asyncio


async def test_register(test_cli):
    rand_username = username()
    rand_password = secrets.token_hex(15)
    rand_email = email()
    rand_discrim = "%04d" % random.randint(0000, 9999)
    rand_discord = f"{hexs()}#{rand_discrim}"
    resp = await test_cli.post(
        "/api/auth/register",
        json={
            "username": rand_username,
            "password": rand_password,
            "email": rand_email,
            "discord_user": rand_discord,
        },
    )

    assert resp.status_code == 200

    row = await test_cli.app.db.fetchrow(
        """
        SELECT user_id FROM users
        WHERE username = $1
        """,
        rand_username,
    )

    assert row is not None
    user_id = row["user_id"]

    try:
        assert test_cli.app._email_list
        assert test_cli.app._webhook_list
    finally:
        async with test_cli.app.app_context():
            task = await delete_user(user_id, delete=True)
            await asyncio.shield(task)
