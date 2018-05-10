import pytest

import sys
import os
import secrets
import random
import io
import base64

sys.path.append(os.getcwd())

import aiohttp
from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username, login_normal


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))

async def test_upload(test_cli):
    """Test that the upload route works given test data!"""
    utoken = await login_normal(test_cli)
    
    print(utoken)
    data = aiohttp.FormData()

    data.add_field('file',
                   io.BytesIO(base64.b64decode(b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABC'
                                               b'AQAAAC1HAwCAAAAC0lEQVQYV2NgYAAAAAM'
                                               b'AAWgmWQ0AAAAASUVORK5CYII=')),
                   filename='random.png',
                   content_type='image/png')

    resp = await test_cli.post('/api/upload', headers={
        'Authorization': utoken,
    }, data=data)

    assert resp.status == 200
    respjson = await resp.json()
    assert isinstance(respjson, dict)
    assert isinstance(respjson['url'], str)
