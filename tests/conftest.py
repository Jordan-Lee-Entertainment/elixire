# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

import sys
import os

sys.path.append(os.getcwd())

from elixire.run import app as mainapp
from elixire.tests.common import token, username, \
        login_normal, login_admin


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))

