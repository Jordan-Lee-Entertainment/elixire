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
from quart import Quart
from winter import SnowflakeFactory

from api.storage import Storage
from api.common.utils import LockStorage
from tests.common.helpers import setup_test_app

from manage.cmd import ban, files, find, user, migration, domains
from .errors import PrintException, ArgError


log = logging.getLogger(__name__)


async def connect_db(config):
    """Connect to databases."""
    pool = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis_pool(
        config.redis, minsize=1, maxsize=3, encoding="utf-8"
    )

    return pool, redis


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


async def shutdown(app):
    await app.db.close()
    app.redis.close()
    await app.redis.wait_closed()
    await app.session.close()


async def amain(loop, config, argv: List[str], *, test: bool = False):
    app = Quart(__name__)
    conn, redis = await connect_db(config)
    app.db = conn
    app.redis = redis
    app.loop = loop
    app.locks = LockStorage()
    app.econfig = config

    app.storage = Storage(app)
    app.winter_factory = SnowflakeFactory()
    app.session = aiohttp.ClientSession()
    app.sched = JobManager(db=conn, context_function=app.app_context)

    if test:
        setup_test_app(loop, app)

    # load our setup() calls on manage/cmd files
    parser = set_parser()

    async def _ctx_wrapper(args):
        # app = ctx.make_app()
        async with app.app_context():
            app._test = test
            await args.func(args)

    try:
        if not argv:
            parser.print_help()
            return app, 0

        args = parser.parse_args(argv)
        await _ctx_wrapper(args)
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
