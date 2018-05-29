import pytest

import sys
import os
import secrets

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


async def test_non_admin(test_cli):
    utoken = await login_normal(test_cli)

    resp = await test_cli.get('/api/admin/test', headers={
        'Authorization': utoken,
    })

    assert resp.status != 200
    assert resp.status == 403


async def test_admin(test_cli):
    utoken = await login_admin(test_cli)

    resp = await test_cli.get('/api/admin/test', headers={
        'Authorization': utoken,
    })

    assert resp.status == 200
    data = await resp.json()

    assert isinstance(data, dict)
    assert data['admin']
