#!/usr/bin/env python3.6
import sys
import asyncio

import aiohttp
import asyncpg
import aioredis

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)
    old_filename = sys.argv[1]
    new_filename = sys.argv[2]

    domain = await db.fetchval("""
    SELECT domain
    FROM files
    WHERE filename = $1
    """, old_filename)

    exec_out = await db.execute("""
    UPDATE files
    SET filename = $1
    WHERE filename = $2
    AND deleted = false
    """, new_filename, old_filename)

    print(f"db out: {exec_out}")

    # invalidate etc
    await redis.delete(f'fspath:{domain}:{old_filename}')
    await redis.delete(f'fspath:{domain}:{new_filename}')

    await db.close()
    redis.close()
    await redis.wait_closed()
    print('OK')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
