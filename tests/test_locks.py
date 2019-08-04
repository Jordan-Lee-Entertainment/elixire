# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio


async def test_locks(test_cli):
    """Test LockStorage"""
    locks = test_cli.app.locks

    delete_files_locks = locks["delete_files"]
    semaphore = delete_files_locks["test"]
    assert isinstance(semaphore, asyncio.Semaphore)

    ban_locks = locks["bans"]
    lock = ban_locks["test"]
    assert isinstance(lock, asyncio.Lock)
