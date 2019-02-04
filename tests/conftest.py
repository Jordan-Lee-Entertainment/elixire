# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

import sys
import os

sys.path.append(os.getcwd())

from run import app as mainapp

from .mock import MockAuditLog


@pytest.yield_fixture
def app():
    app_ = mainapp
    app_.test = True

    # use mock instances of some external services.
    app_.audit_log = MockAuditLog()

    yield app_


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))
