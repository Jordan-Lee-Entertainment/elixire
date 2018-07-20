import pytest

import sys
import os

sys.path.append(os.getcwd())

from elixire.run import app as mainapp
from elixire.tests.common import login_normal


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_stats(test_cli):
    utoken = await login_normal(test_cli)

    resp = await test_cli.get('/api/stats', headers={
        'Authorization': utoken,
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)

    assert isinstance(rjson['total_files'], int)
    assert isinstance(rjson['total_deleted_files'], int)
    assert isinstance(rjson['total_bytes'], (float, int))
    assert isinstance(rjson['total_shortens'], int)
