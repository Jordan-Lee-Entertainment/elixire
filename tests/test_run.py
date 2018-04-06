import pytest

import sys
import os

sys.path.append(os.getcwd())

from elixire.run import app as mainapp
import elixire.tests.creds


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


async def test_login(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 200
    resp_json = await response.json()
    assert isinstance(resp_json['token'], str)


async def test_login_badinput(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
    })

    assert response.status == 400


async def test_login_badpwd(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
        'password': 'AAAAAAAAAAAAAAAAAAAAAAAAAA',
    })

    assert response.status == 403

async def test_login_baduser(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': 'AAAAAAAAAAAAAAAAAAA',
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 403

