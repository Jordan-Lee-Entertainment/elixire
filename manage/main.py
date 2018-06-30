import argparse
import secrets
import asyncio
import logging
import sys
from collections import namedtuple
from pathlib import Path

import bcrypt
import asyncpg
import aioredis

from api.snowflake import get_snowflake
from api.bp.profile import delete_user

log = logging.getLogger(__name__)
Context = namedtuple('ArgContext', 'args db redis loop')


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
    The user will be activated by default.
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


async def deletefiles(ctx):
    """cleanup_files

    Delete all files that are marked as deleted in the image directory.
    This is a legacy operation for instances that did not update
    to a version that deletes files.
    """
    to_delete = await ctx.db.fetch("""
    SELECT fspath
    FROM files
    WHERE files.deleted = true
    """)

    print(f'deleting {len(to_delete)} files')
    completed = 0

    for row in to_delete:
        fspath = row['fspath']
        path = Path(fspath)
        try:
            path.unlink()
            completed += 1
        except FileNotFoundError:
            print(f'fspath {fspath!r} not found')

    print(f"""
    out of {len(to_delete)} files to be deleted
    {completed} were actually deleted
    """)


async def rename_file(ctx):
    """rename_file <shortname> <renamed>

    Rename a single file to another shortname.
    """
    try:
        shortname, renamed = ctx.args.args[:2]
    except ValueError:
        return print('not enough arguments')

    domain = await ctx.db.fetchval("""
    SELECT domain
    FROM files
    WHERE filename = $1
    """, shortname)

    if domain is None:
        return print(f'no files found with shortname {shortname!r}')

    existing_id = await ctx.db.fetchval("""
    SELECT file_id
    FROM files
    WHERE filename = $1
    """, renamed)

    if existing_id:
        return print(f'file {renamed} already exists, stopping!')

    await ctx.db.execute("""
    UPDATE files
    SET filename = $1
    WHERE filename = $2
    AND deleted = false
    """, renamed, shortname)

    # invalidate etc
    await ctx.redis.delete(f'fspath:{domain}:{shortname}')
    await ctx.redis.delete(f'fspath:{domain}:{renamed}')

    print('OK')


async def del_user(ctx):
    """delete_user <username>

    Delete a single user. This does not deactivate the user,
    so it will delete all information.
    """
    try:
        username = ctx.args.args[0]
    except IndexError:
        return print('No username provided')

    userid = await ctx.db.fetchval("""
    SELECT user_id
    FROM users
    WHERE username = $1
    """, username)

    if not userid:
        return print('no user found')

    task = await delete_user(ctx, userid, True)
    await asyncio.shield(task)

    print('OK')


OPERATIONS = {
    'list': ('List all available operations', list_ops),
    'help': ('Get help for an operation', manage_help),
    'adduser': ('Add a user into the instance', adduser),
    'cleanup_files': ('Delete files from the images folder', deletefiles),
    'rename_file': ('Rename a single file', rename_file),
    'deluser': ('Delete a user and their files', del_user),
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

    ctx = Context(args, db, redis, loop)

    try:
        _desc, func = OPERATIONS[args.operation]
        loop.run_until_complete(func(ctx))
    except KeyError:
        print('invalid operation')
    except Exception:
        log.exception('oops.')

    loop.run_until_complete(close_ctx(ctx))
