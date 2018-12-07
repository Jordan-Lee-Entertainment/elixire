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

from elixire.run import app as mainapp
from elixire.tests.common import login_normal, login_admin


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_stats(test_cli):
    utoken = await login_normal(test_cli)

    resp = await test_cli.get('/api/stats', headers={
        'Authorization': utoken,
    })

    assert resp.status == 200
    rjson = await resp.json()
    assert isinstance(rjson, dict)

    assert isinstance(rjson['total_files'], int)
    assert isinstance(rjson['total_deleted_files'], int)
    assert isinstance(rjson['total_bytes'], (float, int))
    assert isinstance(rjson['total_shortens'], int)


async def test_domains(test_cli):
    # admins always own at least domain 0
    atoken = await login_admin(test_cli)

    resp = await test_cli.get('/api/stats/my_domains', headers={
        'Authorization': atoken
    })

    assert resp.status == 200
    rjson = await resp.json()

    assert isinstance(rjson, dict)
    assert isinstance(rjson['0'], dict)

    info = rjson['0']['info']
    assert isinstance(info['domain'], str)
    assert isinstance(info['permissions'], int)
    assert isinstance(info['cf_enabled'], bool)
    assert isinstance(info['admin_only'], bool)
    assert isinstance(info['official'], bool)

    pub = rjson['0']['stats']
    assert isinstance(pub['users'], int)
    assert isinstance(pub['files'], int)
    assert isinstance(pub['shortens'], int)
