# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from .common import login_normal, login_admin

def _extract_uid(token) -> str:
    split = token.split('.')
    try:
        uid, _ = split
    except ValueError:
        uid, _, _, = split
    return uid


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


async def test_user_fetch(test_cli):
    atoken = await login_admin(test_cli)
    uid = _extract_uid(atoken)

    resp = await test_cli.get(f'/api/admin/users/{uid}', headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert isinstance(rjson['user_id'], str)
    assert isinstance(rjson['username'], str)
    assert isinstance(rjson['active'], bool)
    assert isinstance(rjson['admin'], bool)
    assert isinstance(rjson['domain'], int)
    assert isinstance(rjson['subdomain'], str)
    assert isinstance(rjson['consented'], bool) or rjson['consented'] is None
    assert isinstance(rjson['email'], str)
    assert isinstance(rjson['paranoid'], bool)
    assert isinstance(rjson['limits'], dict)

    # trying to fetch the user from the username we got
    # should also work
    resp = await test_cli.get(
        f'/api/admin/users/by-username/{rjson["username"]}', headers={
            'Authorization': atoken
        })

    assert resp.status == 200
    rjson = await resp.json()

    # just checking the id should work, as the response of
    # /by-username/ is the same as doing it by ID.
    assert isinstance(rjson['id'], str)


async def test_user_activate_cycle(test_cli):
    # logic here is to:
    # - deactivate user
    # - check the user's profile, make sure its deactivated
    # - activate user
    # - check profile again, making sure its activated
    ntoken = await login_normal(test_cli)
    atoken = await login_admin(test_cli)

    uid = _extract_uid(ntoken)

    # deactivate
    resp = await test_cli.post(f'/api/admin/deactivate/{uid}', headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert rjson['success']

    # check profile for deactivation
    resp = await test_cli.get(f'/api/admin/users/{uid}', headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)
    assert not rjson['active']

    # activate
    resp = await test_cli.post(f'/api/admin/activate/{uid}', headers={
        'Authorization': atoken
    })
    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert rjson['success']

    # check profile
    resp = await test_cli.get(f'/api/admin/users/{uid}', headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)
    assert rjson['active']


async def test_user_search(test_cli):
    """Test seaching of users."""
    # there isnt much other testing than calling the route
    # and checking for the data types...

    # no idea how we would test all the query arguments
    # in the route.
    atoken = await login_admin(test_cli)

    resp = await test_cli.get('/api/admin/users/search', headers={
        'Authorization': atoken,
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert isinstance(rjson['results'], list)

    pag = rjson['pagination']
    assert isinstance(pag, dict)
    assert isinstance(pag['total'], int)
    assert isinstance(pag['current'], int)


async def test_domain_stats(test_cli):
    """Get instance-wide domain stats."""
    atoken = await login_admin(test_cli)

    resp = await test_cli.get('/api/admin/domains', headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()

    # not the best data validation...
    assert isinstance(rjson, dict)
    for domain in rjson.values():
        assert isinstance(domain, dict)
        assert isinstance(domain['info'], dict)
        assert isinstance(domain['stats'], dict)
        assert isinstance(domain['public_stats'], dict)


async def test_domain_patch(test_cli):
    """Test editing of a single domain."""
    atoken = await login_admin(test_cli)
    utoken = await login_normal(test_cli)

    admin_id = _extract_uid(atoken)
    user_id = _extract_uid(utoken)

    resp = await test_cli.patch('/api/admin/domains/0', json={
        'owner_id': user_id,
        'admin_only': True,
        'official': True,
        'permissions': 666,
    }, headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)

    fields = rjson['updated']
    assert isinstance(fields, list)
    assert 'owner_id' in fields
    assert 'admin_only' in fields
    assert 'official' in fields
    assert 'permissions' in fields

    # fetch domain info
    resp = await test_cli.get('/api/admin/domains/0', headers={
        'Authorization': atoken,
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    dinfo = rjson['info']
    assert isinstance(dinfo, dict)
    assert dinfo['owner']['user_id'] == user_id
    assert dinfo['admin_only']
    assert dinfo['official']
    assert dinfo['permissions'] == 666

    # reset the domain properties
    # to sane defaults
    resp = await test_cli.patch('/api/admin/domains/0', json={
        'owner_id': admin_id,
        'admin_only': False,
        'official': False,
        'permissions': 3,
    }, headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)

    fields = rjson['updated']
    assert isinstance(fields, list)
    assert 'owner_id' in fields
    assert 'admin_only' in fields
    assert 'official' in fields
    assert 'permissions' in fields

    # fetch domain info, again, to make sure.
    resp = await test_cli.get('/api/admin/domains/0', headers={
        'Authorization': atoken,
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    dinfo = rjson['info']
    assert isinstance(dinfo, dict)
    assert dinfo['owner']['user_id'] == admin_id
    assert not dinfo['admin_only']
    assert not dinfo['official']
    assert dinfo['permissions'] == 3


async def test_user_patch(test_cli):
    atoken = await login_admin(test_cli)
    utoken = await login_normal(test_cli)

    user_id = _extract_uid(utoken)

    # request 1: change default user to admin, etc
    resp = await test_cli.patch(f'/api/admin/user/{user_id}', json={
        'upload_limit': 1000,
        'shorten_limit': 1000,
    }, headers={
        'Authorization': atoken,
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, list)
    assert 'upload_limit' in rjson
    assert 'shorten_limit' in rjson

    # request 2: check by getting user info
    resp = await test_cli.get(f'/api/admin/users/{user_id}', headers={
        'Authorization': atoken,
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)
    assert isinstance(rjson['limits'], dict)
    assert rjson['limits']['limit'] == 1000
    assert rjson['limits']['shortenlimit'] == 1000

    # request 3: changing it back
    resp = await test_cli.patch(f'/api/admin/user/{user_id}', json={
        'upload_limit': 104857600,
        'shorten_limit': 100,
    }, headers={
        'Authorization': atoken,
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, list)
    assert 'upload_limit' in rjson
    assert 'shorten_limit' in rjson

async def test_my_stats_as_admin(test_cli):
    """Test the personal domain stats route but as an admin."""
    utoken = await login_admin(test_cli)

    resp = await test_cli.get('/api/stats/my_domains', headers={
        'Authorization': utoken,
    })

    assert resp.status == 200

    rjson = await resp.json()
    assert isinstance(rjson, dict)

    try:
        domain_id = next(iter(rjson.keys()))
    except StopIteration:
        # we can't test if the admin user doesn't own any domains
        # and that is a possible case of the environment.
        return

    dom = rjson[domain_id]

    info = dom['info']
    assert isinstance(info['domain'], str)
    assert isinstance(info['official'], bool)
    assert isinstance(info['admin_only'], bool)
    assert isinstance(info['permissions'], int)

    stats = dom['stats']
    assert isinstance(stats['users'], int)
    assert isinstance(stats['files'], int)
    assert isinstance(stats['size'], int)
    assert isinstance(stats['shortens'], int)
