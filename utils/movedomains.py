#!/usr/bin/env python3.6
import sys
import asyncio

import asyncpg
import aioredis

from common import open_db, close_db


async def main():
    db, redis = await open_db()
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

    await close_db(db, redis)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
