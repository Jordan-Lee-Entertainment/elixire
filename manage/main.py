# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import argparse
import logging
from typing import List

import aiohttp
import asyncpg
import aioredis
from violet import JobManager

from api.storage import Storage
from api.common.utils import LockStorage
from tests.conftest import setup_test_app

from manage.cmd import ban, files, find, user, migration, domains
from .errors import PrintException, ArgError
from .utils import Context


log = logging.getLogger(__name__)


async def connect_db(config, loop):
    """Connect to databases."""
    pool = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis_pool(
        config.redis, minsize=1, maxsize=3, loop=loop, encoding="utf-8"
    )

    return pool, redis


async def close_ctx(ctx: Context) -> None:
    """Close database connections."""
    await ctx.db.close()
    ctx.redis.close()
    await ctx.redis.wait_closed()
    await ctx.session.close()


def set_parser() -> argparse.ArgumentParser:
    """Initialize parser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="operations")

    # start our "blueprints"
    user(subparsers)
    files(subparsers)
    find(subparsers)
    ban(subparsers)
    migration(subparsers)
    domains(subparsers)

    return parser


async def amain(loop, config, argv: List[str], *, test: bool = False):
    conn, redis = await connect_db(config, loop)
    ctx = Context(config, conn, redis, loop, LockStorage())

    # this needs an actual connection to the database and redis
    # so we first instantiate Context, then set the attribute
    ctx.storage = Storage(ctx)
    ctx.session = aiohttp.ClientSession()

    app = ctx.make_app()
    if test:
        setup_test_app(loop, app)

    ctx.sched = JobManager(loop=ctx.loop, db=ctx.db, context_function=app.app_context)
    app.sched = ctx.sched

    # load our setup() calls on manage/cmd files
    parser = set_parser()

    async def _ctx_wrapper(ctx, args):
        # app = ctx.make_app()
        async with app.app_context():
            await args.func(ctx, args)

    try:
        if not argv:
            parser.print_help()
            return 0

        args = parser.parse_args(argv)
        await (_ctx_wrapper(ctx, args))
    except PrintException as exc:
        print(exc.args[0])
    except ArgError as exc:
        print(f'argument error: {",".join(exc.args)}')
        return 1
    except Exception:
        log.exception("oops.")
        return 1
    finally:
        await ctx.close()

    return 0
