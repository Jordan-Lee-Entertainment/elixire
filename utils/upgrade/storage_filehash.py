#!/usr/bin/env python3.6

"""
storage_filehash.py

    Change current image directory structure to account for
    file hashing patches in 
"""

import sys
import asyncio
import hashlib
from pathlib import Path

import asyncpg
import aioredis

p = Path('.')
sys.path.append(str(p.cwd()))
import config

async def open_db():
    db = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)
    return db, redis

async def close_db(db, redis):
    await db.close()
    redis.close()
    await redis.wait_closed()
    print('CLOSE: END')
    

def calculate_md5(image):
    hash_md5 = hashlib.md5()

    with open(image, "rb") as fhandler:
        for chunk in iter(lambda: fhandler.read(4096), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()


async def main():
    pool, redis = await open_db()
    impath = Path('./images')

    images = [path for path in impath.glob('*/*') if path.is_file()]

    total = len(images)
    count = 0
    for image in images:
        print('working on', str(image), count, 'out of', total)
        # calculate md5 of image, move it to another path
        # then alter fspath
        md5_hash = calculate_md5(image)

        spl = str(image).split('.')

        ext = spl[-1]
        imname = spl[-2].split('/')[-1]

        target = impath / md5_hash[0] / f'{md5_hash}.{ext}'
        image.rename(target)

        domain = await pool.fetchval("""
        SELECT domain
        FROM files
        WHERE filename = $1
        """, imname)

        execout = await pool.execute("""
        UPDATE files
        SET fspath = $2
        WHERE filename = $1
        """, f'./{imname!s}', str(target))

        print(f'{imname}: {execout} <= {target}')
        count += 1
        await redis.delete(f'fspath:{domain}:{imname}')

    await close_db(pool, redis)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
