#!/usr/bin/env python3.6
import sys
import aiohttp
import os
import asyncio

import asyncpg

sys.path.append('..')
import config

aiosession = aiohttp.ClientSession()


async def main():
    db = await asyncpg.create_pool(**config.db)
    filename = sys.argv[1]

    exec_out = await db.execute("""
    UPDATE files
    SET deleted = false
    WHERE filename = $1
    AND deleted = true
    """, filename)

    print(f"db out: {exec_out}")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
