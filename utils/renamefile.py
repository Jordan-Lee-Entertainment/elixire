#!/usr/bin/env python3.6
import sys
import asyncio

import asyncpg

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)
    old_filename = sys.argv[1]
    new_filename = sys.argv[2]

    exec_out = await db.execute("""
    UPDATE files
    SET filename = $1
    WHERE filename = $2
    AND deleted = false
    """, new_filename, old_filename)

    print(f"db out: {exec_out}")
    await db.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
