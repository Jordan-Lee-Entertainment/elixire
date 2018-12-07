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

import pytest

import sys
import os
import secrets

sys.path.append(os.getcwd())

from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username, login_normal


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_login(test_cli):
    response = await test_cli.post('/api/login', json={
        'user': elixire.tests.creds.USERNAME,
        'password': elixire.tests.creds.PASSWORD,
    })

    assert response.status == 200
    resp_json = await response.json()
    assert isinstance(resp_json, dict)
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


async def test_no_token(test_cli):
    """Test no token request."""
    response = await test_cli.get('/api/profile', headers={})
    assert response.status == 403


async def test_invalid_token(test_cli):
    """Test invalid token."""
    response = await test_cli.get('/api/profile', headers={
        'Authorization': token(),
    })
    assert response.status == 403


async def test_valid_token(test_cli):
    token = await login_normal(test_cli)
    response_valid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_valid.status == 200


async def test_revoke(test_cli):
    token = await login_normal(test_cli)

    response_valid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_valid.status == 200

    revoke_call = await test_cli.post('/api/revoke', json={
        'user': elixire.tests.creds.USERNAME,
        'password': elixire.tests.creds.PASSWORD
    })

    assert revoke_call.status == 200

    response_invalid = await test_cli.get('/api/profile', headers={
        'Authorization': token,
    })

    assert response_invalid.status == 403
