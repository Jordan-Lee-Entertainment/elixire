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



