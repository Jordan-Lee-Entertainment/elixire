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
from run import app as real_app

# load mocking utils
import tests.util.mock  # noqa


@pytest.fixture(name="event_loop", scope="session")
def event_loop_fixture():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def setup_test_app(event_loop, given_app) -> None:
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
