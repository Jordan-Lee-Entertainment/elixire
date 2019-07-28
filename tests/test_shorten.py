# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest
from .common import token, username, login_normal

@pytest.mark.asyncio
async def test_invalid_shorten(test_cli):
    invalid_shit = [f'{username()}' for _ in range(100)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f'/s/{invalid}')
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_shorten(test_cli):
    utoken = await login_normal(test_cli)

    resp = await test_cli.post('/api/shorten', headers={
        'Authorization': utoken
    }, json={
        'url': 'https://elixi.re'
    })

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)
    assert isinstance(data['url'], str)


@pytest.mark.asyncio
async def test_shorten_complete(test_cli):
    utoken = await login_normal(test_cli)
    url = 'https://elixi.re'

    resp = await test_cli.post('/api/shorten', headers={
        'Authorization': utoken,
    }, json={
        'url': url,
    })

    assert resp.status_code == 200
    data = await resp.json
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
    try:
        key = next(k for k in shortens if k == given_shorten)
        shorten = shortens[key]
    except StopIteration:
        raise RuntimeError('shorten not found')

    assert shorten['redirto'] == url

@pytest.mark.asyncio
async def test_shorten_wrong_scheme(test_cli):
    utoken = await login_normal(test_cli)

    some_schemes = [
        'ftp://',
        'mailto:',
        'laksjdkj::',
        token(),
    ]

    # bad idea but whatever
    wrong = []
    for scheme in some_schemes:
        wrong += [f'{scheme}{token()}.{token()}' for _ in range(100)]

    for wrong_url in wrong:
        resp = await test_cli.post('/api/shorten', headers={
            'Authorization': utoken
        }, json={
            'url': wrong_url,
        })

        assert resp.status_code == 400
