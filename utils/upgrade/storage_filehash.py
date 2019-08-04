#!/usr/bin/env python3.6
# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


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

p = Path(".")
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
    print("CLOSE: END")


def calculate_hash(image) -> str:
    hashobj = hashlib.sha256()

    with open(image, "rb") as fhandler:
        for chunk in iter(lambda: fhandler.read(4096), b""):
            hashobj.update(chunk)

    return hashobj.hexdigest()


async def main():
    pool, redis = await open_db()
    impath = Path("./images")

    images = [path for path in impath.glob("*/*") if path.is_file()]

    total = len(images)
    count = 0
    for image in images:
        print("working on", str(image), count, "out of", total)
        # calculate md5 of image, move it to another path
        # then alter fspath
        md5_hash = calculate_hash(image)

        simage = str(image)
        target = None
        shortname = None

        if simage.find(".") != -1:
            spl = str(image).split(".")

            ext = spl[-1]
            shortname = spl[-2].split("/")[-1]

            target = impath / md5_hash[0] / f"{md5_hash}.{ext}"
        else:
            shortname = simage.split("/")[-1]
            target = impath / md5_hash[0] / md5_hash

        image.rename(target)

        domain = await pool.fetchval(
            """
            SELECT domain
            FROM files
            WHERE filename = $1
            """,
            shortname,
        )

        execout = await pool.execute(
            """
            UPDATE files
            SET fspath = $2
            WHERE filename = $1
            """,
            shortname,
            f"./{target!s}",
        )

        print(f"{shortname}: {execout} <= {target}")
        count += 1
        await redis.delete(f"fspath:{domain}:{shortname}")

    await close_db(pool, redis)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
