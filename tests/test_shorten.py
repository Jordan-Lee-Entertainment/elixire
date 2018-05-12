import pytest

import sys
import os
import secrets
import random

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

async def test_invalid_shorten(test_cli):
    invalid_shit = [f'{username()}' for _ in range(100)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f'/s/{invalid}')
        assert resp.status == 404


async def test_shorten(test_cli):
    utoken = await login_normal(test_cli)

    resp = await test_cli.post('/api/shorten', headers={
        'Authorization': utoken
    }, json={
        'url': 'https://elixi.re'
    })

    assert resp.status == 200
    data = await resp.json()
    assert isinstance(data, dict)
    assert isinstance(data['url'], str)


async def test_shorten_complete(test_cli):
    utoken = await login_normal(test_cli)
    url = 'https://elixi.re'

    resp = await test_cli.post('/api/shorten', headers={
        'Authorization': utoken,
    }, json={
        'url': url,
    })

    assert resp.status == 200
    data = await resp.json()
    assert isinstance(data, dict)
    assert isinstance(data['url'], str)

    given_shorten = data['url'].split('/')[-1]

    # No, we can't call GET /s/whatever to test this route.
    # and probably that won't happen to GET /i/whatever too.
    # because since this is a test server, it runs in an entirely
    # different domain (127.0.0.1:random_port), instead of
    # localhost:8081.
    listdata = await test_cli.get('/api/list?page=0', headers={
        'Authorization': utoken,
    })

    assert listdata.status == 200

    listdata = await listdata.json()

    shortens = listdata['shortens']
    print(given_shorten)
    print(shortens)
    try:
        key = next(k for k in shortens if k == given_shorten)
        shorten = shortens[key]
    except StopIteration:
        raise RuntimeError('shorten not found')

    assert shorten['redirto'] == url
