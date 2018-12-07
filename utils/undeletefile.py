#!/usr/bin/env python3.6
"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

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
