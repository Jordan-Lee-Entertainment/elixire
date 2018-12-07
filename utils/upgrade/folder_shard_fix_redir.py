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


"""
./folder_shard_fix_redir.py

    Fix files that were renamed and are now broken
    from the folder_sharding.py script.
"""

import asyncio
import sys

from pathlib import Path

p = Path('.')
sys.path.append(str(p.cwd()))

import asyncpg
import aioredis

import config


async def main():
    pool = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)

    imroot = Path('./images')

    # expensive op
    all_files = await pool.fetch("""
    SELECT filename, fspath, domain
    FROM files
    """)

    print(f'checking {len(all_files)} files')

    for filedata in all_files:
        filename = filedata['filename']
        fspath = filedata['fspath']
        domain = filedata['domain']

        fspath_name_complete = fspath.split('/')[-1]
        fspath_name = fspath_name_complete.split('.')[0]

        if filename != fspath_name:
            new_fspath = imroot / fspath_name[0] / fspath_name_complete

            if str(fspath) == f'./{new_fspath}':
                print(f'ignoring {filename}')
                continue

            print(f'updating {filename} fspath (old fspath: {fspath}) '
                  f'(new fspath: {new_fspath})')

            # update, invalidate!

            await pool.execute("""
            UPDATE files
            SET fspath = $2
            WHERE filename = $1
            """, filename, f'./{new_fspath}')

            await redis.delete(f'fspath:{domain}:{filename}')

    await pool.close()
    redis.close()
    await redis.wait_closed()
    print('OK')

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
