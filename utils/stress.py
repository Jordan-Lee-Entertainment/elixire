#!/usr/bin/env python3.6

import asyncio
import aiohttp

TASKS = 100
# in seconds
TIMEOUT = 1

URL = 'http://localhost:8081'


async def request(session):
    # existing user, wrong password
    async with session.post(f'{URL}/api/login', json={
            'user': 'luna',
            'password': 'ass',
        }) as r:
        return r

async def request_image(session):
    async with session.get(f'{URL}/i/gkk.jpg') as r:
        return r


async def main(loop):
    tasks = TASKS
    coros = []
    session = aiohttp.ClientSession()

    while True:
        for _ in range(tasks):
            task = loop.create_task(request(session))
            coros.append(task)

        done, pending = await asyncio.wait(coros, timeout=TIMEOUT)

        print(f'done: {len(done)}, pending={len(pending)}')

        if pending:
            break

        tasks *= 2

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
