import pytest

import sys
import os

sys.path.append(os.getcwd())

import elixire.tests.creds
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
    assert isinstance(resp_json['name'], str)
    assert isinstance(resp_json['version'], str)


async def test_api_features(test_cli):
    resp = await test_cli.get('/api/features')

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson['uploads'], bool)
    assert isinstance(rjson['shortens'], bool)
    assert isinstance(rjson['registrations'], bool)
    assert isinstance(rjson['pfupdate'], bool)
