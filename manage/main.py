import argparse
import asyncio
import sys
from collections import namedtuple

import asyncpg
import aioredis

Context = namedtuple('ArgContext', 'args db redis')


async def connect_db(config, loop):
    pool = await asyncpg.create_pool(**config.db)
    redis = await aioredis.create_redis_pool(
        config.redis,
        minsize=1, maxsize=3,
        loop=loop, encoding='utf-8'
    )

    return pool, redis


async def list_ops(args):
    print('All available operations:')
    for name in OPERATIONS:
        desc, _ = OPERATIONS[name]
        print(f'\t{name}: {desc}')


OPERATIONS = {
    'list': ('List all available operations', list_ops),
}


parser = argparse.ArgumentParser()
parser.add_argument('operation', help='a management operation '
                                      '(list lists all available operations)')


def main(config):
    if len(sys.argv) < 2:
        parser.print_help()
        return

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    db, redis = loop.run_until_complete(connect_db(config, loop))

    ctx = Context(args, db, redis)
    print(ctx)

    try:
        _desc, func = OPERATIONS[args.operation]
        loop.run_until_complete(func(ctx))
    except KeyError:
        print('invalid operation')
