#!/usr/bin/env python3.6
import sys
import asyncio
import asyncpg

sys.path.append('..')
import config


async def main():
    db = await asyncpg.create_pool(**config.db)

    # Total non-deleted file count
    all_nd_files = await db.fetch("""
    SELECT *
    FROM files
    WHERE deleted = false
    """)
    nd_file_count = len(all_nd_files)

    # Total deleted file count
    all_d_files = await db.fetch("""
    SELECT *
    FROM files
    WHERE deleted = true
    """)
    d_file_count = len(all_d_files)

    # Total non-deleted shortens
    all_nd_shortens = await db.fetch("""
    SELECT *
    FROM shortens
    WHERE deleted = false
    """)
    nd_shorten_count = len(all_nd_shortens)

    # Total deleted shortens
    all_d_shortens = await db.fetch("""
    SELECT *
    FROM shortens
    WHERE deleted = true
    """)
    d_shorten_count = len(all_d_shortens)

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
    total_nd_file_count_week = await db.fetch("""
    SELECT *
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """)
    nd_file_count_week = len(total_nd_file_count_week)

    # Total deleted file uploads in last week
    total_d_file_count_week = await db.fetch("""
    SELECT *
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """)
    d_file_count_week = len(total_d_file_count_week)

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
    total_nd_shorten_count_week = await db.fetch("""
    SELECT *
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """)
    nd_shorten_count_week = len(total_nd_shorten_count_week)

    # Total deleted shortens in last week
    total_d_shorten_count_week = await db.fetch("""
    SELECT *
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """)
    d_shorten_count_week = len(total_d_shorten_count_week)

    # Total active user count
    total_active_users = await db.fetch("""
    SELECT *
    FROM users
    WHERE active = true
    """)
    total_active_user_count = len(total_active_users)

    # Total inactive user count
    total_inactive_users = await db.fetch("""
    SELECT *
    FROM users
    WHERE active = false
    """)
    total_inactive_user_count = len(total_inactive_users)

    # Biggest file
    biggest_file = await db.fetchrow("""
    SELECT filename, file_size
    FROM files
    ORDER BY file_size DESC
    """)

    # Smallest file
    smallest_file = await db.fetchrow("""
    SELECT filename, file_size
    FROM files
    ORDER BY file_size ASC
    """)

    print("Users\n"
          "=====\n"
          f"Total active user count: {total_active_user_count}\n"
          f"Total inactive user count: {total_inactive_user_count}\n\n"
          "Files\n"
          "=====\n"
          f"Global Counts, ND: {nd_file_count}, D: {d_file_count}\n"
          f"Weekly Counts, ND: {nd_file_count_week}, D: {d_file_count_week}\n"
          f"Global sizes, ND: {total_nd_file_size}b, D: {total_d_file_size}b\n"
          f"Weekly sizes, ND: {total_nd_file_size_week}b, "
          f"D: {total_d_file_size_week}b\n"
          f"Biggest file: {biggest_file['filename']} at "
          f"{biggest_file['file_size']}b\n\n"
          f"Smallest file: {smallest_file['filename']} at "
          f"{smallest_file['file_size']}b\n\n"
          "Shortens\n"
          "========\n"
          f"Global Counts, ND: {nd_shorten_count}, D: {d_shorten_count}\n"
          f"Weekly Counts, ND: {nd_shorten_count_week}, "
          f"D: {d_shorten_count_week}\n")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
