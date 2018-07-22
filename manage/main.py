import argparse
import datetime
import secrets
import asyncio
import logging
import sys

from collections import namedtuple
from pathlib import Path

import bcrypt
import asyncpg
import aioredis

from api.snowflake import get_snowflake, snowflake_time
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
    for name in sorted(OPERATIONS):
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
    so it will delete all information, including files.

    Proceed with extreme caution as there is no going
    back from this operation.
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


def account_delta(user_id):
    tstamp = snowflake_time(user_id)
    tstamp = datetime.datetime.fromtimestamp(tstamp)
    return datetime.datetime.utcnow() - tstamp


async def get_counts(ctx, user_id) -> str:
    files = await ctx.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE files.uploader = $1
    """, user_id)

    shortens = await ctx.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE files.uploader = $1
    """, user_id)

    return f'{files} files, {shortens} shortens'


async def find_inactive_users(ctx):
    """Find inactive users.

    The criteria for inactive users are accounts
    that are deactivated AND are older than 2 weeks.
    """
    uids = await ctx.db.fetch("""
    SELECT username, user_id
    FROM users
    WHERE users.active = false
      AND now() - snowflake_time(user_id) > interval '2 weeks'
    """)

    for row in uids:
        delta = account_delta(row['user_id'])
        cinfo = await get_counts(ctx, row['user_id'])
        print(f'\t- {row["username"]} {row["user_id"]}, '
              f'{cinfo}, created {delta}')


async def find_unused_accs(ctx):
    """Find unused accounts.

    The criteria for unused accounts are users
    that have no files for a month.
    """

    users = await ctx.db.fetch("""
    SELECT username, user_id
    FROM users
    """)

    for row in users:
        uid = row['user_id']

        inactive = await ctx.db.fetchval("""
        SELECT (now() - snowflake_time(MAX(file_id))) > interval '1 month'
        FROM files
        WHERE files.uploader = $1
        """, uid)

        if not inactive:
            continue

        delta = account_delta(row['user_id'])
        counts = await get_counts(ctx, row['user_id'])
        print(f'\t- {row["username"]} {row["user_id"]}, '
              f'{counts}, created {delta}')


OPERATIONS = {
    'list': ('List all available operations', list_ops),
    'help': ('Get help for an operation', manage_help),
    'adduser': ('Add a user into the instance', adduser),
    'cleanup_files': ('Delete files from the images folder', deletefiles),
    'rename_file': ('Rename a single file', rename_file),
    'deluser': ('Delete a user and their files', del_user),
    'find_inactive': ('Find inactive users', find_inactive_users),
    'find_unused': ('Find unused accounts', find_unused_accs),
}


def set_parser():
    """Initialize parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', help='a management operation '
                                          '("list" lists all '
                                          'available operations)')
    parser.add_argument('args', help='arguments to the operation', nargs='*')

    return parser


def main(config):
    parser = set_parser()

    if len(sys.argv) < 2:
        parser.print_help()
        return

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    conn, redis = loop.run_until_complete(connect_db(config, loop))

    ctx = Context(args, conn, redis, loop)

    try:
        _desc, func = OPERATIONS[args.operation]
        loop.run_until_complete(func(ctx))
    except KeyError:
        print('invalid operation')
    except Exception:
        log.exception('oops.')

    loop.run_until_complete(close_ctx(ctx))
