# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import aiohttp
from .creds import USERNAME, PASSWORD
from .common import token, username, email, login_normal


@pytest.mark.asyncio
async def test_profile_work(test_cli):
    """Test the profile user, just getting data."""
    utoken = await login_normal(test_cli)
    resp = await test_cli.get('/api/profile', headers={
        'Authorization': utoken
    })

    assert resp.status_code == 200
    rjson = await resp.json
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

    # test_stats already checks data
    assert isinstance(rjson['stats'], dict)

    dstatus = rjson['dump_status']
    assert isinstance(dstatus, dict)
    assert isinstance(dstatus['state'], str)


@pytest.mark.asyncio
async def test_limits_work(test_cli):
    utoken = await login_normal(test_cli)
    resp = await test_cli.get('/api/limits', headers={
        'Authorization': utoken
    })

    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)

    assert isinstance(rjson['limit'], int)
    assert isinstance(rjson['used'], int)
    assert rjson['used'] <= rjson['limit']

    assert isinstance(rjson['shortenlimit'], int)
    assert isinstance(rjson['shortenused'], int)
    assert rjson['shortenused'] <= rjson['shortenlimit']


@pytest.mark.asyncio
async def test_patch_profile(test_cli):
    utoken = await login_normal(test_cli)

    # request 1: getting profile info to
    # change back to later
    profileresp = await test_cli.get('/api/profile', headers={
        'Authorization': utoken
    })

    assert profileresp.status_code == 200
    profile = await profileresp.json
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
        'password': PASSWORD,
    })

    assert resp.status_code == 200
    rjson = await resp.json

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
        'username': USERNAME,
        'email': profile['email'],
        'paranoid': False,
        'password': PASSWORD,
    })

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson, dict)
    assert isinstance(rjson['updated_fields'], list)

    # making sure...
    assert 'username' in rjson['updated_fields']
    assert 'email' in rjson['updated_fields']
    assert 'paranoid' in rjson['updated_fields']


@pytest.mark.asyncio
async def test_profile_wrong_token(test_cli):
    """Test the profile route with wrong tokens."""
    for _ in range(50):
        resp = await test_cli.get('/api/profile', headers={
            'Authorization': token()
        })

        assert resp.status_code == 403
