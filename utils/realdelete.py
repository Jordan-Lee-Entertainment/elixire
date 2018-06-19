#!/usr/bin/env python3.6

import asyncio
import sys
from pathlib import Path


p = Path('.')
sys.path.append(str(p.cwd()))

from common import open_db, close_db

async def main():
    db, redis = await open_db()

    deleted_paths = await db.fetch("""
    SELECT fspath
    FROM files
    WHERE files.deleted = true
    """)

    # go through each path, delete it.
    print(f'working through {len(deleted_paths)} paths')
    complete = 0

    for row in deleted_paths:
        fspath = row['fspath']
        path = Path(fspath)
        try:
            path.unlink()
            complete += 1
        except FileNotFoundError:
            print(f'failed for {fspath!r}')

    print(f'deleted {complete} files out of {len(deleted_paths)}')

    await close_db(db, redis)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
