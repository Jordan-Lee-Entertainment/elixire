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

sys.path.append('..')
import config
from common import open_db, close_db

aiosession = aiohttp.ClientSession()


async def purge_cf_cache(econfig, file_name: str, base_urls):
    """Clear the Cloudflare cache for the given URL."""

    if not econfig.CF_PURGE:
        print('Cloudflare purging is disabled.')
        return

    cf_purge_url = "https://api.cloudflare.com/client/v4/zones/"\
                   f"{econfig.CF_ZONEID}/purge_cache"

    purge_urls = [file_url + file_name for file_url in base_urls]

    cf_auth_headers = {
        'X-Auth-Email': econfig.CF_EMAIL,
        'X-Auth-Key': econfig.CF_APIKEY
    }

    purge_payload = {
        'files': purge_urls,
    }

    async with aiosession.delete(cf_purge_url,
                                 json=purge_payload,
                                 headers=cf_auth_headers) as resp:
        return resp


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
    SET deleted = true
    WHERE filename = $1
    AND deleted = false
    """, filename)

    print(f"db out: {exec_out}")
    await redis.delete(f'fspath:{domain}:{filename}')

    if config.CF_PURGE:
        print("cf purging")
        file_path = await db.fetchval("""
        SELECT fspath
        FROM files
        WHERE filename = $1
        AND deleted = true
        """, filename)

        full_filename = os.path.basename(file_path)

        cfres = await purge_cf_cache(config, full_filename,
                                     config.CF_UPLOADURLS)
        print(f"purge result: {cfres}")

    await close_db(db, redis)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
