import pytest

import sys
import os
import secrets

sys.path.append(os.getcwd())

from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username


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
        'password': token(),
    })

    assert response.status == 403


async def test_login_baduser(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': username(),
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 403

# token tests


async def test_no_token(test_cli):
    """Test no token request."""
    response = await test_cli.get('/api/profile', headers={})
    assert response.status == 400


async def test_invalid_token(test_cli):
    """Test invalid token."""
    response = await test_cli.get('/api/profile', headers={
        'Authorization': token(),
    })
    assert response.status == 403


async def test_valid_token(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 200
    data = await response.json()
    assert isinstance(data, dict)

    token = data['token']
    response_valid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_valid.status == 200

