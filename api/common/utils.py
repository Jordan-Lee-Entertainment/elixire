import asyncio
from collections import defaultdict


def int_(val):
    if val is None:
        return None

    return int(val)


def _semaphore(num):
    def _wrap():
        return asyncio.Semaphore(num)
    return _wrap


class LockStorage:
    _fields = (
        ('delete_files', _semaphore(10)),
    )

    def __init__(self):
        self._locks = {}

        for field, typ in self._fields:
            self._locks[field] = defaultdict(typ)

    def __getitem__(self, key):
        return self._locks[key]
