import pytest

import sys
import os
import secrets
import random

sys.path.append(os.getcwd())

import aiohttp
from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username, login_normal, png_data


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def check_exists(test_cli, shortname, utoken, not_exists=False):
    """Check if a file exists, given the shortname, token, etc."""
    resp = await test_cli.get('/api/list?page=0', headers={
        'Authorization': utoken,
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson['files'], dict)

    if not_exists:
        assert shortname not in rjson['files']
    else:
        assert shortname in rjson['files']


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

    assert resp.status == 200
    respjson = await resp.json()
    assert isinstance(respjson, dict)
    assert isinstance(respjson['url'], str)
    assert isinstance(respjson['delete_url'], str)
    await check_exists(test_cli, respjson['shortname'], utoken)


async def test_delete_file(test_cli):
    utoken = await login_normal(test_cli)
    data = aiohttp.FormData()

    data.add_field('file', png_data(),
                   filename='random.png',
                   content_type='image/png')

    resp = await test_cli.post('/api/upload', headers={
        'Authorization': utoken,
    }, data=data)

    assert resp.status == 200
    respjson = await resp.json()
    assert isinstance(respjson, dict)
    assert isinstance(respjson['url'], str)
    await check_exists(test_cli, respjson['shortname'], utoken)

    # test delete
    resp_del = await test_cli.delete('/api/delete', headers={
        'Authorization': utoken
    }, json={
        'filename': respjson['shortname']
    })

    assert resp_del.status == 200
    rdel_json = await resp_del.json()
    assert isinstance(rdel_json, dict)
    assert rdel_json['success']

    await check_exists(test_cli, respjson['shortname'], utoken, True)


async def test_delete_nonexist(test_cli):
    utoken = await login_normal(test_cli)
    resp_del = await test_cli.delete('/api/delete', headers={
        'Authorization': utoken
    }, json={
        'filename': 'lkdjklfjkgkghkkhsfklhjslkdfjglakdfjl'
    })

    assert resp_del.status == 404
