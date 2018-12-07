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

sys.path.append(os.getcwd())

import aiohttp
from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username, email, login_normal


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_profile_work(test_cli):
    """Test the profile user, just getting data."""
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

    # dict checking is over the test_limits_work function
    assert isinstance(rjson['limits'], dict)


async def test_limits_work(test_cli):
    utoken = await login_normal(test_cli)
    resp = await test_cli.get('/api/limits', headers={
        'Authorization': utoken
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)

    assert isinstance(rjson['limit'], int)
    assert isinstance(rjson['used'], int)
    assert rjson['used'] <= rjson['limit']

    assert isinstance(rjson['shortenlimit'], int)
    assert isinstance(rjson['shortenused'], int)
    assert rjson['shortenused'] <= rjson['shortenlimit']


async def test_patch_profile(test_cli):
    utoken = await login_normal(test_cli)

    # request 1: getting profile info to
    # change back to later
    profileresp = await test_cli.get('/api/profile', headers={
        'Authorization': utoken
    })

    assert profileresp.status == 200
    profile = await profileresp.json()
    assert isinstance(profile, dict)

    # request 2: updating profile
    new_uname = username()

    resp = await test_cli.patch('/api/profile', headers={
        'Authorization': utoken
    }, json={
        # change to a random username
        'username': f'test{new_uname}',

        # random email
        'email': email(),

        # users dont have paranoid by default, so
        # change that too. the more we change,
        # the better
        'paranoid': True,
        'password': elixire.tests.creds.PASSWORD,
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert isinstance(rjson['updated_fields'], list)

    # check if api acknowledged our updates
    assert 'username' in rjson['updated_fields']
    assert 'email' in rjson['updated_fields']
    assert 'paranoid' in rjson['updated_fields']

    # request 3: changing profile info back
    resp = await test_cli.patch('/api/profile', headers={
        'Authorization': utoken
    }, json={
        'username': elixire.tests.creds.USERNAME,
        'email': profile['email'],
        'paranoid': False,
        'password': elixire.tests.creds.PASSWORD,
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert isinstance(rjson['updated_fields'], list)

    # making sure...
    assert 'username' in rjson['updated_fields']
    assert 'email' in rjson['updated_fields']
    assert 'paranoid' in rjson['updated_fields']


async def test_profile_wrong_token(test_cli):
    """Test the profile route with wrong tokens."""
    for _ in range(50):
        resp = await test_cli.get('/api/profile', headers={
            'Authorization': token()
        })

        assert resp.status == 403
