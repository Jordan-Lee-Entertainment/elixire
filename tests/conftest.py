# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest
import asyncio

import sys
import os

from quart import current_app

sys.path.append(os.getcwd())

# we import the app so that we can inject our own things
# or override configuration values. drawback is that the test
# fixture for the app is also called "app". to prevent misuse of either
# of those variables, naming here dictates that main_app is the actual
# app object that everyone uses, while app is the test fixture that has
# automatic startup and shutdown in the pytest lifetime cycle.
from run import app as real_app, _setup_working_directory_folders

from api.common.user import create_user
from api.common.auth import gen_token
from api.bp.profile import delete_user

from tests.util.client import TestClientWithUser
from tests.common import hexs, email

# load mocking utils (automatically monkeypatches)
import tests.util.mock  # noqa


@pytest.fixture(name="event_loop", scope="session")
def event_loop_fixture():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def setup_test_app(event_loop, given_app) -> None:
    _setup_working_directory_folders()

    given_app.loop = event_loop
    given_app.econfig.CLOUDFLARE = False
    given_app.econfig.DUMP_ENABLED = True
    given_app.econfig.NOTIFY_ACTIVATION_EMAILS = True

    given_app.econfig.RATELIMITS = {"*": (10000, 1)}

    # TODO mock metrics manager so we don't have to disable metrics here
    given_app.econfig.ENABLE_METRICS = False

    given_app._test_email_list = []


def setup_mocks(given_app):
    given_app.audit_log = tests.util.mock.MockAuditLog()
    given_app.resolv = tests.util.mock.MockResolver()


@pytest.fixture(name="app", scope="session")
async def app_fixture(event_loop):
    setup_test_app(event_loop, real_app)
    async with real_app.app_context():
        await real_app.startup()

    setup_mocks(real_app)
    yield real_app

    async with real_app.app_context():
        await real_app.shutdown()


@pytest.fixture(name="test_cli")
def test_cli_fixture(app):
    return app.test_client()


async def _create_test_user(*, admin: bool = False) -> dict:
    username = f"elixire-test-user-{hexs(6)}"
    password = hexs(6)
    user_email = email()

    user = await create_user(
        username=username, password=password, email=user_email, active=True
    )
    user_token = gen_token(user)

    if admin:
        await current_app.db.execute(
            "UPDATE users SET admin = true WHERE user_id = $1", user["user_id"]
        )

    return {
        **user,
        **{
            "token": user_token,
            "email": user_email,
            "username": username,
            "password": password,
        },
    }


async def _delete_test_user(user: dict):
    task = await delete_user(user["user_id"], delete=True)
    await asyncio.shield(task)


@pytest.fixture(name="test_user", scope="session")
async def test_user_fixture(app):
    """Yield a randomly generated test user.

    As an optimization, the test user is set to be in session scope,
    the test client's cleanup() method then proceeds to reset the test user
    back to a wanted initial state, which is faster than creating/destroying
    the user on every single test.
    """
    async with app.app_context():
        user = await _create_test_user()

    yield user

    async with app.app_context():
        await _delete_test_user(user)


@pytest.fixture(name="quick_test_user", scope="function")
async def quick_test_user_fixture(app):
    """Same as test_user but on function scope, only use for tests that are
    highly destructive to the test user in ways that can't be reset (like
    a user deletion test)."""
    async with app.app_context():
        user = await _create_test_user()

    yield user

    async with app.app_context():
        await _delete_test_user(user)


@pytest.fixture(name="test_user_admin", scope="session")
async def test_user_admin_fixture(app):
    """Yield a randomly generated test user that is an admin."""
    async with app.app_context():
        user = await _create_test_user(admin=True)

    yield user

    async with app.app_context():
        await _delete_test_user(user)


@pytest.fixture(scope="function")
async def test_cli_user(test_cli, test_user):
    """Yield a TestClient instance that contains a randomly generated
    user."""
    client = TestClientWithUser(test_cli, test_user)
    yield client
    await client.cleanup()


@pytest.fixture(scope="function")
async def test_cli_quick_user(test_cli, quick_test_user):
    """Yield a TestClient instance that contains a randomly generated
    user that will be destroyed after the test (instead of reset).

    Use this sparingly, as creating/deleting users is expensive in terms
    of test suite time.
    """
    client = TestClientWithUser(test_cli, quick_test_user)
    yield client
    await client.cleanup()


async def _set_owner(domain_id, user_id):
    await current_app.db.execute(
        """
        INSERT INTO domain_owners (domain_id, user_id)
        VALUES ($1, $2)
        ON CONFLICT ON CONSTRAINT domain_owners_pkey
        DO UPDATE
            SET user_id = $2
            WHERE domain_owners.domain_id = $1
        """,
        domain_id,
        user_id,
    )


@pytest.fixture(scope="function")
async def test_cli_admin(test_cli, test_user_admin):
    """Yield a TestClient instance that contains a randomly generated
    admin user."""
    client = TestClientWithUser(test_cli, test_user_admin)
    async with client.app.app_context():
        old_owner_id = await current_app.db.fetchval(
            "SELECT user_id FROM domain_owners WHERE domain_id=0"
        )
        await _set_owner(0, client.id)

    yield client

    async with client.app.app_context():
        await _set_owner(0, old_owner_id)

    await client.cleanup()
