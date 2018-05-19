#!/usr/bin/env python3.6
import sys
import secrets
import asyncio

import bcrypt
import asyncpg
import aioredis

sys.path.append('..')
import config
import api.snowflake as snowflake


async def main():
    db = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)

    email = sys.argv[1]
    username = sys.argv[2]

    # generate password
    user_id = snowflake.get_snowflake()

    try:
        password = sys.argv[3]
    except IndexError:
        password = secrets.token_urlsafe(25)

    _pwd = bytes(password, 'utf-8')
    hashed = bcrypt.hashpw(_pwd, bcrypt.gensalt(14))

    # insert on db
    await db.execute("""
    INSERT INTO users (user_id, username, password_hash, email)
    VALUES ($1, $2, $3, $4)
    """, user_id, username, hashed.decode('utf-8'), email)

    await db.execute("""
    INSERT INTO limits (user_id)
    VALUES ($1)
    """, user_id)
    print('inserted')

    await redis.delete(f'uid:{username}')
    print('invalidated redis key')

    # print the user & password
    print(f'user id: {user_id!r}')
    print(f'username: {username!r}')
    print(f'password: {password!r}')

    await db.close()
    redis.close()
    await redis.wait_closed()
    print('OK')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
