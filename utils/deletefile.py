#!/usr/bin/env python3.6
import sys
import secrets
import asyncio

import bcrypt
import asyncpg

sys.path.append('..')
import api.snowflake as snowflake
import config

import aiohttp
import os

aiosession = aiohttp.ClientSession()

async def purge_cf_cache(econfig, file_name: str, base_urls):
    """Clear the Cloudflare cache for the given URL."""

    if not econfig.CF_PURGE:
        print('Cloudflare purging is disabled.')
        return

    cf_purge_url = "https://api.cloudflare.com/client/v4/zones/"\
                   f"{econfig.CF_ZONEID}/purge_cache"

    purge_urls = [file_url+file_name for file_url in base_urls]

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
    db = await asyncpg.create_pool(**config.db)
    filename = sys.argv[1]

    exec_out = await db.execute("""
    UPDATE files
    SET deleted = true
    WHERE filename = $1
    AND deleted = false
    """, filename)

    print(f"db out: {exec_out}")

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


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
