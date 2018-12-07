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

import asyncio
from collections import defaultdict


def int_(val, default=None):
    if val is None:
        return None or default

    return int(val)


def _semaphore(num):
    def _wrap():
        return asyncio.Semaphore(num)
    return _wrap


class LockStorage:
    _fields = (
        ('delete_files', _semaphore(10)),
        ('bans', asyncio.Lock),
    )

    def __init__(self):
        self._locks = {}

        for field, typ in self._fields:
            self._locks[field] = defaultdict(typ)

    def __getitem__(self, key):
        return self._locks[key]
