#!/usr/bin/env python3.6
import sys
import asyncio

import asyncpg
import aioredis

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)
    filename = sys.argv[1]
    new_domain = int(sys.argv[2])

    old_domain = await db.fetchval("""
    SELECT domain
    FROM files
    WHERE filename = $1
    """, filename)

    exec_out = await db.execute("""
    UPDATE files
    SET domain = $1
    WHERE filename = $2
    """, new_domain, filename)

    print(f"db out: {exec_out}")

    await redis.delete(f'fspath:{old_domain}:{filename}')

    await db.close()
    await redis.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
