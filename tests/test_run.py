import pytest

import sys
import os

sys.path.append(os.getcwd())

from elixire.run import app as mainapp


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_api(test_cli):
    response = await test_cli.get('/api/hello')
    assert response.status == 200
    resp_json = await response.json()
    assert resp_json['name'] == 'elixire'
