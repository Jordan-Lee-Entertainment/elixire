# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import sys

import asyncpg
import aioredis

sys.path.append('..')
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
    
