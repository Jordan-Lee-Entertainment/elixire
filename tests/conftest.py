# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest
import asyncio

import sys
import os

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


async def _create_test_user() -> dict:
    username = f"elixire-test-user-{hexs(6)}"
    password = hexs(6)
    user_email = email()

    user = await create_user(username, password, user_email, active=True)
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


@pytest.fixture(scope="function")
async def test_cli_user(test_cli, test_user):
    """Yield a TestClient instance that contains a randomly generated
    user."""
    client = TestClientWithUser(test_cli, test_user)
    yield client
    await client.cleanup()
