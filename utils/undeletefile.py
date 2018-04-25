#!/usr/bin/env python3.6
import sys
import aiohttp
import os
import asyncio

import asyncpg
import aioredis

sys.path.append('..')
import config

aiosession = aiohttp.ClientSession()


async def main():
    db = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)
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

    await db.close()
    redis.close()
    await redis.wait_closed()
    print('OK')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
