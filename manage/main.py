# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - manage.py main code
"""
import argparse
import asyncio
import logging
import sys

import aiohttp
import asyncpg
import aioredis

# import stuff from api for our Context.
# more info on Context @ manage/utils.py
from api.storage import Storage
from api.common.utils import LockStorage
from api.jobs import JobManager

from .errors import PrintException, ArgError
from .utils import Context

from manage.cmd import ban, files, find, user, migration

log = logging.getLogger(__name__)


async def connect_db(config, loop):
    """Connect to databases."""
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
    await ctx.session.close()


def set_parser():
    """Initialize parser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='operations')

    # start our "blueprints"
    user(subparsers)
    files(subparsers)
    find(subparsers)
    ban(subparsers)
    migration(subparsers)

    return parser


async def _make_sess(ctx):
    ctx.session = aiohttp.ClientSession()


def main(config):
    loop = asyncio.get_event_loop()
    conn, redis = loop.run_until_complete(connect_db(config, loop))

    # construct our context
    ctx = Context(conn, redis, loop, LockStorage())

    # this needs an actual connection to the database and redis
    # so we first instantiate Context, then set the attribute
    ctx.storage = Storage(ctx)

    ctx.sched = JobManager(loop)

    # aiohttp warns us when making ClientSession out of
    # a coroutine, so yeah.
    loop.run_until_complete(_make_sess(ctx))

    # load our setup() calls on manage/cmd files
    parser = set_parser()

    try:
        if len(sys.argv) < 2:
            parser.print_help()
            return

        args = parser.parse_args()
        loop.run_until_complete(args.func(ctx, args))
    except PrintException as exc:
        print(exc.args[0])
    except ArgError as exc:
        print(f'argument error: {",".join(exc.args)}')
        return 1
    except Exception:
        log.exception('oops.')
        return 1
    finally:
        loop.run_until_complete(close_ctx(ctx))

    return 0
