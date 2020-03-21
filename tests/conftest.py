# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import os
import sys

import pytest

sys.path.append(os.getcwd())

from api.common.user import create_user, delete_user  # noqa: E402
from api.common.auth import gen_token  # noqa: E402
from api.models.domain import Domain  # noqa: E402
from run import app as app_  # noqa: E402
from .mock import MockAuditLog  # noqa: E402
from .common import hexs, email, TestClient  # noqa: E402


@pytest.yield_fixture(name="event_loop", scope="session")
def event_loop_fixture():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(name="app", scope="session")
async def app_fixture(event_loop):
    app_._test = True
    app_.loop = event_loop
    app_.econfig.RATELIMITS = {"*": (10000, 1)}

    # TODO should we keep this as false?
    app_.econfig.ENABLE_METRICS = False

    # use mock instances of some external services.
    app_.audit_log = MockAuditLog()

    # used in internal email/webhook functions for testing
    app_._email_list = []
    app_._webhook_list = []

    # event_loop.run_until_complete(app_.startup())
    await app_.startup()

    yield app_

    # event_loop.run_until_complete(app_.shutdown())
    await app_.shutdown()


@pytest.fixture(name="test_cli")
def test_cli_fixture(app):
    return app.test_client()


# this code started first in mr 52
# https://gitlab.com/elixire/elixire/merge_requests/52
# now its being redone with that code + litecord code
# https://gitlab.com/litecord/litecord/merge_requests/42
async def _user_fixture_setup():
    username = hexs(6)
    password = hexs(6)
    user_email = email()

    user = await create_user(username, password, user_email)
    user_token = gen_token(user)

    return {
        **user,
        **{
            "token": user_token,
            "email": user_email,
            "username": username,
            "password": password,
        },
    }


async def _user_fixture_teardown(user: dict):
    task = await delete_user(user["user_id"], delete=True)
    await asyncio.shield(task)


@pytest.fixture(name="test_user")
async def test_user_fixture(app):
    """Yield a randomly generated test user."""
    async with app.app_context():
        user = await _user_fixture_setup()

    yield user

    async with app.app_context():
        await _user_fixture_teardown(user)


@pytest.fixture
async def test_cli_user(test_cli, test_user):
    """Yield a TestClient instance that contains a randomly generated
    user."""
    client = TestClient(test_cli, test_user)
    yield client
    await client.cleanup()


@pytest.fixture
async def test_cli_admin(test_cli):
    """Yield a TestClient with an admin user."""
    # This does not use the test_user because if a given test uses both
    # test_cli_user and test_cli_admin, test_cli_admin will just point to that
    # same test_cli_user, which isn't acceptable.
    app = test_cli.app

    async with app.app_context():
        test_user = await _user_fixture_setup()

    user_id = test_user["user_id"]

    await app.db.execute(
        """
        UPDATE users SET admin = true WHERE user_id = $1
        """,
        user_id,
    )

    async with app.app_context():
        root_domain = await Domain.fetch(0)
        assert root_domain is not None

        old_owner = await root_domain.fetch_owner()

    async with app.app_context():
        await root_domain.set_owner(test_user["user_id"])

    client = TestClient(test_cli, test_user)
    yield client
    await client.cleanup()

    async with app.app_context():
        await _user_fixture_teardown(test_user)
        if old_owner is not None:
            await root_domain.set_owner(old_owner.id)
