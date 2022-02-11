# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - manage.py main code
"""
import argparse
import asyncio
import logging
from typing import List

import aiohttp
import asyncpg
import aioredis
from quart import Quart

# import stuff from api for our Context.
# more info on Context @ manage/utils.py
from api.storage import Storage
from api.common.utils import LockStorage
from api.jobs import JobManager

from .errors import PrintException, ArgError

from manage.cmd import ban, files, find, user, migration
from tests.conftest import setup_test_app, setup_mocks

log = logging.getLogger(__name__)


async def connect_db(config, loop):
    """Connect to databases."""
    pool = await asyncpg.create_pool(**config.db)

    redis_pool = aioredis.ConnectionPool.from_url(
        config.redis,
        max_connections=11,
        encoding="utf-8",
        decode_responses=True,
    )
    redis = aioredis.Redis(connection_pool=redis_pool)

    return pool, redis_pool, redis


async def shutdown(app):
    """Close database connections."""
    await app.db.close()
    await app.redis_pool.disconnect()
    app.sched.stop()
    await app.session.close()


def set_parser():
    """Initialize parser."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="operations")

    # start our "blueprints"
    user(subparsers)
    files(subparsers)
    find(subparsers)
    ban(subparsers)
    migration(subparsers)

    return parser


async def _make_sess(ctx):
    ctx.session = aiohttp.ClientSession()


async def amain(loop, config, argv: List[str], *, is_testing: bool = False):
    loop = asyncio.get_event_loop()
    conn, redis_pool, redis = await connect_db(config, loop)
    app = Quart(__name__)
    app.db = conn
    app.redis_pool = redis_pool
    app.redis = redis
    app.loop = loop
    app.econfig = config

    app.storage = Storage(app)
    app.locks = LockStorage()
    app.session = aiohttp.ClientSession()
    app.sched = JobManager()

    if is_testing:
        setup_test_app(loop, app)
        setup_mocks(app)

    # load our setup() calls on manage/cmd files
    parser = set_parser()

    try:
        if not argv:
            parser.print_help()
            return app, 0

        args = parser.parse_args(argv)

        async with app.app_context():
            await args.func(args)
    except PrintException as exc:
        print(exc.args[0])
    except ArgError as exc:
        print(f'argument error: {",".join(exc.args)}')
        return app, 1
    except Exception:
        log.exception("oops.")
        return app, 1
    finally:
        await shutdown(app)

    return app, 0
