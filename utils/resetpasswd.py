#!/usr/bin/env python3.6
import sys
import secrets
import asyncio

import bcrypt
import asyncpg

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)
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

    # print the user & password
    print(f'db output: {dbout}')
    print(f'username: {username!r}')
    print(f'password: {password!r}')

    await db.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
