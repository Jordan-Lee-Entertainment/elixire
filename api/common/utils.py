# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
from typing import Optional, Any
from collections import defaultdict


def int_(val: Optional[Any], default: Optional[int] = None) -> Optional[int]:
    """Tries to convert the given variable to int.
    Returns None or the value given in the default parameter."""

    # this check is required for mypy to catch that we're
    # checking val's optional-ility
    if val is None:
        return default

    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _semaphore(num):
    """Return a function that when called, returns a new semaphore with the
    given counter."""

    def _wrap():
        return asyncio.Semaphore(num)

    return _wrap


class LockStorage:
    """A storage class to hold locks and semaphores.

    This is a wrapper around a defaultdict so it can hold
    multiple defaultdicts, one for each field declared in _fields.
    """

    _fields = (("delete_files", _semaphore(10)), ("bans", asyncio.Lock))

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
