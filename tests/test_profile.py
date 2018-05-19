import pytest

import sys
import os

sys.path.append(os.getcwd())

import aiohttp
from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username, login_normal


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))

async def test_profile_work(test_cli):
    utoken = await login_normal(test_cli)
    resp = await test_cli.get('/api/profile', headers={
        'Authorization': utoken
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)
    assert isinstance(rjson['user_id'], str)
    assert isinstance(rjson['username'], str)
    assert isinstance(rjson['active'], bool)
    assert isinstance(rjson['admin'], bool)
    assert rjson['consented'] in (True, False, None)
    assert isinstance(rjson['subdomain'], str)
    assert isinstance(rjson['domain'], int)
    assert isinstance(rjson['limits'], dict)


async def test_profile_wrong_token(test_cli):
    for _ in range(200):
        resp = await test_cli.get('/api/profile', headers={
            'Authorization': token()
        })

        assert resp.status == 403
