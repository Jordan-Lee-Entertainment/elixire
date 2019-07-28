# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

import sys
import os

sys.path.append(os.getcwd())

from run import app, set_blueprints
from .mock import MockAuditLog


@pytest.fixture(name="app")
def app_fixture(event_loop):
    app._test = True
    app.loop = event_loop
    app.econfig.RATELIMITS = {"*": (10000, 1)}

    # use mock instances of some external services.
    app.audit_log = MockAuditLog()

    event_loop.run_until_complete(app.startup())
    yield app
    event_loop.run_until_complete(app.shutdown())


@pytest.fixture
def test_cli(app):
    return app.test_client()
