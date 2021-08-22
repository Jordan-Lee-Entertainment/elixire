# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
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
        ("delete_files", _semaphore(10)),
        ("bans", asyncio.Lock),
    )

    def __init__(self):
        self._locks = {}

        for field, typ in self._fields:
            self._locks[field] = defaultdict(typ)

    def __getitem__(self, key):
        return self._locks[key]


def find_different_keys(dict1: dict, dict2: dict) -> list:
    """Find the keys that point to different values in two dicts."""
    keys = []

    for key in dict1:
        if dict1[key] != dict2.get(key):
            keys.append(key)

    return keys
