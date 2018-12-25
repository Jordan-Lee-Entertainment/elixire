#!/usr/bin/env python3.6
# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import sys
import aiohttp
import os
import asyncio

import asyncpg
import aioredis

from common import open_db, close_db

aiosession = aiohttp.ClientSession()


async def main():
    db, redis = await open_db()
    filename = sys.argv[1]

    domain = await db.fetchval("""
    SELECT domain
    FROM files
    WHERE filename = $1
    """, filename)

    exec_out = await db.execute("""
    UPDATE files
    SET deleted = false
    WHERE filename = $1
    AND deleted = true
    """, filename)

    print(f"db out: {exec_out}")
    await redis.delete(f'fspath:{domain}:{filename}')

    await close_db(db, redis)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
