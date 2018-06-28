import argparse
import secrets
import asyncio
import sys
from collections import namedtuple

import bcrypt
import asyncpg
import aioredis

from api.snowflake import get_snowflake

Context = namedtuple('ArgContext', 'args db redis')


async def connect_db(config, loop):
    """Connect to databases"""
    pool = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis_pool(
        config.redis,
        minsize=1, maxsize=3,
        loop=loop, encoding='utf-8'
    )

    return pool, redis


async def close_ctx(ctx):
    """Close database connections."""
    await ctx.db.close()
    ctx.redis.close()
    await ctx.redis.wait_closed()


async def list_ops(_ctx):
    """list

    List all available operations on the manage script.
    """
    print('All available operations:')
    for name in OPERATIONS:
        desc, _ = OPERATIONS[name]
        print(f'\t{name}: {desc}')


async def manage_help(ctx):
    """help <operation>

    Get help for a certain operation.
    """
    try:
        operation = ctx.args.args[0]
    except IndexError:
        await list_ops(ctx)
        return

    try:
        _desc, func = OPERATIONS[operation]
    except KeyError:
        return print('unknown operation')

    print(func.__doc__)


async def adduser(ctx):
    """adduser <email> <username> [password]

    Add a single user on the current instance.
    When password is not provided, a secure one is generated.
    """
    try:
        email, username, = ctx.args.args[:2]
    except ValueError:
        return print('invalid number of arguments')

    try:
        password = ctx.args.args[2]
    except IndexError:
        password = secrets.token_urlsafe(25)

    pass_hashing = password.encode()
    hashed = bcrypt.hashpw(pass_hashing, bcrypt.gensalt(14))

    user_id = get_snowflake()

    await ctx.db.execute("""
    INSERT INTO users (user_id, username, password_hash, email)
    VALUES ($1, $2, $3, $4)
    """, user_id, username, hashed.decode(), email)

    await ctx.db.execute("""
    INSERT INTO limits (user_id)
    VALUES ($1)
    """, user_id)

    await ctx.redis.delete(f'uid:{username}')

    print(f"""
    user id: {user_id}
    username: {username!r}
    password: {password!r}
    """)


OPERATIONS = {
    'list': ('List all available operations', list_ops),
    'help': ('Get help for an operation', manage_help),
    'adduser': ('Add a user into the instance', adduser),
}


parser = argparse.ArgumentParser()
parser.add_argument('operation', help='a management operation '
                                      '(list lists all available operations)')
parser.add_argument('args', help='arguments to the operation', nargs='*')


def main(config):
    if len(sys.argv) < 2:
        parser.print_help()
        return

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    db, redis = loop.run_until_complete(connect_db(config, loop))

    ctx = Context(args, db, redis)

    try:
        _desc, func = OPERATIONS[args.operation]
        loop.run_until_complete(func(ctx))
    except KeyError:
        print('invalid operation')

    loop.run_until_complete(close_ctx(ctx))
