#!/usr/bin/env python3.6
import os
import asyncio
import asyncpg

from decimal import *

from common import open_db, close_db


def byte_to_mibstring(bytecount):
    if not bytecount:
        return "N/A"
    bytecount = Decimal(bytecount)
    mib = Decimal(bytecount / 1024 / 1024)
    return f"{round(mib, 2)}MiB"


async def main():
    db, _redis = await open_db()

    # Total domain with cf enabled
    cf_domain_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM domains
    WHERE cf_enabled = true
    """)

    # Total domain with cf disabled
    ncf_domain_count = await db.fetchval("""
    SELECT *
    FROM domains
    WHERE cf_enabled = false
    """)

    # Total non-deleted file count
    nd_file_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE deleted = false
    """)

    # Total deleted file count
    d_file_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE deleted = true
    """)

    # Total non-deleted shortens
    nd_shorten_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM shortens
    WHERE deleted = false
    """)

    # Total deleted shortens
    d_shorten_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM shortens
    WHERE deleted = true
    """)

    # Total non-deleted file size
    total_nd_file_size = await db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE deleted = false
    """)

    # Total deleted file size
    total_d_file_size = await db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE deleted = true
    """)

    # Total non-deleted file uploads in last week
    nd_file_count_week = await db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """)

    # Total deleted file uploads in last week
    d_file_count_week = await db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """)

    # Total size of non-deleted file uploads in last week
    total_nd_file_size_week = await db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """)

    # Total size of deleted file uploads in last week
    total_d_file_size_week = await db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """)

    # Total non-deleted shortens in last week
    nd_shorten_count_week = await db.fetchval("""
    SELECT COUNT(*)
    FROM shortens
    WHERE shorten_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """)

    # Total deleted shortens in last week
    d_shorten_count_week = await db.fetchval("""
    SELECT COUNT(*)
    FROM shortens
    WHERE shorten_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """)

    # Total active user count
    total_active_user_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE active = true
    """)

    # Users who are active and consented
    total_consent_user_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE active = true AND consented = true
    """)

    # Total inactive user count
    total_inactive_user_count = await db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE active = false
    """)

    # Biggest file
    biggest_file = await db.fetchrow("""
    SELECT filename, file_size, fspath
    FROM files
    ORDER BY file_size DESC
    """)
    biggest_ext = os.path.splitext(biggest_file["fspath"])[-1]

    # Smallest file
    smallest_file = await db.fetchrow("""
    SELECT filename, file_size, fspath
    FROM files
    ORDER BY file_size ASC
    """)
    smallest_ext = os.path.splitext(smallest_file["fspath"])[-1]

    print(f"""Users
=====
Total active user count: {total_active_user_count}
Total active consented user count: {total_consent_user_count} [public this]

Total inactive user count: {total_inactive_user_count}

Domains
=======
Total CF domains: {cf_domain_count}
Total non-CF domains: {ncf_domain_count}

Files
=====
Global Counts, ND: {nd_file_count}, D: {d_file_count}
Weekly Counts, ND: {nd_file_count_week}, D: {d_file_count_week}
Global sizes, ND: {byte_to_mibstring(total_nd_file_size)}, \
D: {byte_to_mibstring(total_d_file_size)}
Weekly sizes, ND: {byte_to_mibstring(total_nd_file_size_week)}, \
D: {byte_to_mibstring(total_d_file_size_week)}
Biggest file: '{biggest_file['filename']}{biggest_ext}' \
at {byte_to_mibstring(biggest_file['file_size'])}
Smallest file: '{smallest_file['filename']}{smallest_ext}' \
at {byte_to_mibstring(smallest_file['file_size'])}

Shortens
========
Global Counts, ND: {nd_shorten_count}, D: {d_shorten_count}
Weekly Counts, ND: {nd_shorten_count_week}, D: {d_shorten_count_week}
    """)

    await close_db(db, _redis)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
