# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
from collections import defaultdict


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
