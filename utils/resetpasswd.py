#!/usr/bin/env python3.6
import sys
import secrets
import asyncio

import bcrypt
import asyncpg
import aioredis

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis(config.redis)

    username = sys.argv[1]
    password = secrets.token_urlsafe(25)

    _pwd = bytes(password, 'utf-8')
    hashed = bcrypt.hashpw(_pwd, bcrypt.gensalt(14))

    # insert on db
    dbout = await db.execute("""
    UPDATE users
    SET password_hash = $1
    WHERE username = $2
    """, hashed.decode('utf-8'), username)

    # we need uid lol
    uid = await db.fetchval("""
    SELECT user_id
    FROM users
    WHERE username=$1
    """, username)

    # invalidate
    await redis.delete(f'uid:{uid}:password_hash')
    await redis.delete(f'uid:{uid}:active')

    # print the user & password
    print(f'db output: {dbout}')
    print(f'username: {username!r}')
    print(f'password: {password!r}')

    await db.close()
    redis.close()
    await redis.wait_closed()
    print('OK')




if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
