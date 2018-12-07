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

import elixire.tests.creds
from elixire.run import app as mainapp


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
    assert isinstance(resp_json['name'], str)
    assert isinstance(resp_json['version'], str)


async def test_api_features(test_cli):
    resp = await test_cli.get('/api/features')

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson['uploads'], bool)
    assert isinstance(rjson['shortens'], bool)
    assert isinstance(rjson['registrations'], bool)
    assert isinstance(rjson['pfupdate'], bool)
