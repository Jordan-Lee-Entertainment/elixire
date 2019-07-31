# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import secrets
import sys
import os

import pytest

sys.path.append(os.getcwd())

from run import app as app_
from .mock import MockAuditLog
from .common import email, TestClient


@pytest.fixture(name="app")
def app_fixture(event_loop):
    app_._test = True
    app_.loop = event_loop
    app_.econfig.RATELIMITS = {"*": (10000, 1)}

    # TODO should we keep this as false?
    app_.econfig.ENABLE_METRICS = False

    # use mock instances of some external services.
    app_.audit_log = MockAuditLog()

    event_loop.run_until_complete(app_.startup())
    yield app
    event_loop.run_until_complete(app_.shutdown())


@pytest.fixture(name="test_cli")
def test_cli_fixture(app):
    return app.test_client()


# this code started first in mr 52
# https://gitlab.com/elixire/elixire/merge_requests/52
# now its being redone with that code + litecord code
# https://gitlab.com/litecord/litecord/merge_requests/42
async def _user_fixture_setup(app):
    username = secrets.token_hex(6)
    password = secrets.token_hex(6)
    user_email = email()

    # TODO fix

    user_id, pwd_hash = await create_user(
        username, user_email, password, app.db, app.loop
    )

    # generate a token for api access
    user_token = make_token(user_id, pwd_hash)

    return {
        "id": user_id,
        "token": user_token,
        "email": user_email,
        "username": username,
        "password": password,
    }


async def _user_fixture_teardown(app, udata: dict):
    await delete_user(udata["id"], db=app.db)


@pytest.fixture(name="test_user")
async def test_user_fixture(app):
    """Yield a randomly generated test user."""
    udata = await _user_fixture_setup(app)
    yield udata
    await _user_fixture_teardown(app, udata)


@pytest.fixture
async def test_cli_user(test_cli, test_user):
    """Yield a TestClient instance that contains a randomly generated
    user."""
    yield TestClient(test_cli, test_user)


@pytest.fixture
async def test_cli_staff(test_cli):
    """Yield a TestClient with a staff user."""
    # This does not use the test_user because if a given test uses both
    # test_cli_user and test_cli_admin, test_cli_admin will just point to that
    # same test_cli_user, which isn't acceptable.
    app = test_cli.app
    test_user = await _user_fixture_setup(app)
    user_id = test_user["id"]

    await app.db.execute(
        """
    UPDATE users SET admin = true WHERE id = $2
    """,
        user_id,
    )

    yield TestClient(test_cli, test_user)
    await _user_fixture_teardown(test_cli.app, test_user)
