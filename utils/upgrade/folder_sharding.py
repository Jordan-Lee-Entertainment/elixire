#!/usr/bin/env python3.6
# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


"""
./folder_sharding.py
    Upgrade your elixi.re images folder to a new format
    that should bring less issues to the filesystem dealing
    with a folder with thousands of files.
"""

import asyncio
import string
import sys
from pathlib import Path

import asyncpg
import aioredis

p = Path('.')
sys.path.append(str(p.cwd()))

import config


# if alphabet changes in /api/common.py
# change here too
ALPHABET = string.ascii_lowercase + string.digits

async def main():
    pool = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)

    impath = Path('./images')

    for letter in ALPHABET:
        letterpath = impath / letter
        try:
            letterpath.mkdir()
            print('making folder', letterpath)
        except FileExistsError:
            print('already made folder', letterpath)

    images = [path for path in impath.iterdir() if path.is_file()]

    print(f'{len(images)} images')

    renamed, total = 0, 0
    for image in images:
        simg = str(image)
        imfname = simg.split('/')[-1]

        # ne for non extension etc
        imfname_ne = imfname.split('.')[0]

        imletter = imfname[0]
        if imletter not in ALPHABET:
            continue

        total += 1

        target = impath / imletter / imfname
        print(f'renaming {image} to {target}')

        if target.exists():
            print(f"can't rename {image} to {target}, target exists, stopping")
            break

        image.rename(target)

        domain = await pool.fetchval("""
        SELECT domain
        FROM files
        WHERE filename = $1
        """, imfname_ne)

        exec_out = await pool.execute("""
        UPDATE files
        SET fspath = $2
        WHERE filename = $1
        """, imfname_ne, f'./{target}')

        print(f'db out: {exec_out}')
        await redis.delete(f'fspath:{domain}:{imfname_ne}')
        renamed += 1

    print(f'renamed {renamed} out of {total} to rename')

    await pool.close()
    redis.close()
    await redis.wait_closed()
    print('OK')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
