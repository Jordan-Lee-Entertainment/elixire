# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
from typing import Optional, Any, TypeVar
from collections import defaultdict
from quart import send_file as quart_send_file

T = TypeVar("T")


def _maybe_type(typ: type, value: Any, default: Optional[T] = None) -> Optional[T]:
    """Tries to convert the given value to the given type.
    Returns None or the value given in the default
    parameter if it fails."""
    # this check is required for mypy to catch that we're
    # checking the value's nullability
    if value is None:
        return default

    try:
        return typ(value)
    except (TypeError, ValueError):
        return default


def int_(val: Optional[Any], default: Optional[int] = None) -> Optional[int]:
    return _maybe_type(int, val, default)


def dict_(val: Optional[Any], default: Optional[dict] = None) -> Optional[dict]:
    return _maybe_type(dict, val, default)


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


async def send_file(path: str, *, mimetype: Optional[str] = None):
    """Helper function to send files while also supporting Ranged Requests."""
    response = await quart_send_file(path, mimetype=mimetype)
    response.headers["content-length"] = response.response.size
    response.headers["content-security-policy"] = "sandbox; frame-src 'None'"
    return response
