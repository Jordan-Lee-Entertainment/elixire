#!/usr/bin/env python3.6
import sys
import asyncio

import asyncpg

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)
    old_domain = sys.argv[1]
    new_domain = sys.argv[2]

    exec_out = await db.execute("""
    UPDATE files
    SET domain = $1
    WHERE domain = $2
    """, new_domain, old_domain)

    print(f"db out: {exec_out}")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
