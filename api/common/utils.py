# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

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
