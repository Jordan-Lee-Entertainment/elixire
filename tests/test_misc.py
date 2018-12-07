"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import os
import time

import pytest

sys.path.append(os.getcwd())

import elixire.tests.creds
from elixire.run import app as mainapp

from elixire.api.snowflake import _snowflake as time_snowflake, \
    get_snowflake, snowflake_time


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_snowflake(test_cli):
    tstamp = int(time.time() * 1000)
    sflake = time_snowflake(tstamp)
    tstamp2 = snowflake_time(sflake) * 1000

    assert tstamp == tstamp2
