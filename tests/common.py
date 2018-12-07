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

import secrets
import random
import io
import base64
import string

from .creds import USERNAME, PASSWORD, ADMIN_USER, ADMIN_PASSWORD
EMAIL_ALPHABET = string.ascii_lowercase


def choice_repeat(seq, length):
    return ''.join([secrets.choice(seq) for _ in range(length)])


def png_data():
    return io.BytesIO(base64.b64decode(b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABC'
                                       b'AQAAAC1HAwCAAAAC0lEQVQYV2NgYAAAAAM'
                                       b'AAWgmWQ0AAAAASUVORK5CYII='))

def token():
    return secrets.token_urlsafe(random.randint(100, 300))

def username():
    return token()

def email():
    name = choice_repeat(string.ascii_lowercase, 16)
    domain = choice_repeat(string.ascii_lowercase, 16)

    return f'{name}@{domain}.com'


async def login_normal(test_cli) -> str:
    resp = await test_cli.post('/api/login', json={
        'user': USERNAME,
        'password': PASSWORD,
    })

    assert resp.status == 200
    data = await resp.json()
    assert isinstance(data, dict)

    return data['token']


async def login_admin(test_cli) -> str:
    resp = await test_cli.post('/api/login', json={
        'user': ADMIN_USER,
        'password': ADMIN_PASSWORD,
    })

    assert resp.status == 200
    data = await resp.json()
    assert isinstance(data, dict)

    return data['token']
