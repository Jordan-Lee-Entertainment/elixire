# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import aiohttp
import secrets
from .common import login_normal, png_data


async def check_exists(test_cli, shortname, utoken, not_exists=False):
    """Check if a file exists, given the shortname, token, etc."""
    resp = await test_cli.get('/api/list?page=0', headers={
        'Authorization': utoken,
    })

    assert resp.status_code == 200
    rjson = await resp.json

    assert isinstance(rjson['files'], dict)

    if not_exists:
        assert shortname not in rjson['files']
    else:
        assert shortname in rjson['files']


@pytest.mark.asyncio
async def test_upload_png(test_cli):
    """Test that the upload route works given test data"""
    utoken = await login_normal(test_cli)
    data = aiohttp.FormData()

    data.add_field('file', png_data(),
                   filename='random.png',
                   content_type='image/png')

    resp = await test_cli.post('/api/upload', headers={
        'Authorization': utoken,
    }, data=data)

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson['url'], str)
    assert isinstance(respjson['delete_url'], str)
    await check_exists(test_cli, respjson['shortname'], utoken)


@pytest.mark.asyncio
async def test_delete_file(test_cli):
    utoken = await login_normal(test_cli)
    data = aiohttp.FormData()

    data.add_field('file', png_data(),
                   filename='random.png',
                   content_type='image/png')

    resp = await test_cli.post('/api/upload', headers={
        'Authorization': utoken,
    }, data=data)

    assert resp.status_code == 200
    respjson = await resp.json
    assert isinstance(respjson, dict)
    assert isinstance(respjson['url'], str)
    await check_exists(test_cli, respjson['shortname'], utoken)

    # test delete
    short = respjson['shortname']

    resp_del = await test_cli.delete(f'/api/files/{short}', headers={
        'Authorization': utoken
    })

    assert resp_del.status == 204

    await check_exists(test_cli, respjson['shortname'], utoken, True)


@pytest.mark.asyncio
async def test_delete_nonexist(test_cli):
    """Test deletions of files that don't exist."""
    utoken = await login_normal(test_cli)
    rand_file = secrets.token_urlsafe(20)

    resp_del = await test_cli.delete(f'/api/files/{rand_file}', headers={
        'Authorization': utoken
    })

    assert resp_del.status == 404

    # ensure sharex compatibility endpoint works too
    resp_del = await test_cli.get(f'/api/files/{rand_file}/delete', headers={
        'Authorization': utoken
    })

    assert resp_del.status == 404
