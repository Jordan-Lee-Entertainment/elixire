# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import splitext
from pathlib import Path
from decimal import Decimal

from quart import current_app as app
from api.common import delete_file
from manage.errors import PrintException


def byte_to_mibstring(bytecount: int) -> str:
    """Convert an integer representing the
    total amount of bytes to a string
    representing the total amount of
    megabytes."""
    if not bytecount:
        return "N/A"

    bytecount = Decimal(bytecount)
    mib = Decimal(bytecount / 1024 / 1024)
    return f"{round(mib, 2)}MiB"


async def deletefiles(_args):
    """Clean files marked as deleted on the db."""
    to_delete = await app.db.fetch(
        """
    SELECT fspath
    FROM files
    WHERE files.deleted = true
    """
    )

    print(f"deleting {len(to_delete)} files")
    completed = 0

    for row in to_delete:
        fspath = row["fspath"]
        path = Path(fspath)
        try:
            path.unlink()
            completed += 1
        except FileNotFoundError:
            print(f"fspath {fspath!r} not found")

    print(
        f"""
    out of {len(to_delete)} files to be deleted
    {completed} were actually deleted
    """
    )


async def rename_file(args):
    """Rename a file."""
    shortname = args.shortname
    renamed = args.renamed

    domain = await app.db.fetchval(
        """
    SELECT domain
    FROM files
    WHERE filename = $1 AND deleted = false
    """,
        shortname,
    )

    if domain is None:
        return print(f"no files found with shortname {shortname!r}")

    existing_id = await app.db.fetchval(
        """
    SELECT file_id
    FROM files
    WHERE filename = $1
    """,
        renamed,
    )

    if existing_id:
        return print(f"file {renamed} already exists, stopping!")

    exec_out = await app.db.execute(
        """
    UPDATE files
    SET filename = $1
    WHERE filename = $2
    AND deleted = false
    """,
        renamed,
        shortname,
    )

    # invalidate etc
    await app.redis.delete(f"fspath:{domain}:{shortname}")
    await app.redis.delete(f"fspath:{domain}:{renamed}")

    print(f"SQL out: {exec_out}")


async def show_stats(_args):
    db = app.db

    # Total non-deleted file count
    nd_file_count = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE deleted = false
    """
    )

    # Total deleted file count
    d_file_count = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE deleted = true
    """
    )

    # Total non-deleted shortens
    nd_shorten_count = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    WHERE deleted = false
    """
    )

    # Total deleted shortens
    d_shorten_count = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    WHERE deleted = true
    """
    )

    # Total non-deleted file size
    total_nd_file_size = await db.fetchval(
        """
    SELECT SUM(file_size)
    FROM files
    WHERE deleted = false
    """
    )

    # Total deleted file size
    total_d_file_size = await db.fetchval(
        """
    SELECT SUM(file_size)
    FROM files
    WHERE deleted = true
    """
    )

    # Total non-deleted file uploads in last week
    nd_file_count_week = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """
    )

    # Total deleted file uploads in last week
    d_file_count_week = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """
    )

    # Total size of non-deleted file uploads in last week
    total_nd_file_size_week = await db.fetchval(
        """
    SELECT SUM(file_size)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """
    )

    # Total size of deleted file uploads in last week
    total_d_file_size_week = await db.fetchval(
        """
    SELECT SUM(file_size)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """
    )

    # Total non-deleted shortens in last week
    nd_shorten_count_week = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    WHERE shorten_id > time_snowflake(now() - interval '7 days')
    AND deleted = false
    """
    )

    # Total deleted shortens in last week
    d_shorten_count_week = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    WHERE shorten_id > time_snowflake(now() - interval '7 days')
    AND deleted = true
    """
    )

    # Total active user count
    total_active_user_count = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM users
    WHERE active = true
    """
    )

    # Total inactive user count
    total_inactive_user_count = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM users
    WHERE active = false
    """
    )

    # Biggest file
    biggest_file = await db.fetchrow(
        """
    SELECT filename, file_size, fspath
    FROM files
    ORDER BY file_size DESC
    """
    )
    biggest_ext = splitext(biggest_file["fspath"])[-1]

    print(
        f"""Users
=====
{total_active_user_count} active, {total_inactive_user_count} inactive

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

Shortens
========
Global Counts, ND: {nd_shorten_count}, D: {d_shorten_count}
Weekly Counts, ND: {nd_shorten_count_week}, D: {d_shorten_count_week}
    """
    )


async def _extract_file_info(shortname) -> int:
    """Extract the domain ID for a file.

    Does checking against dummy user.
    """
    row = await app.db.fetchrow(
        """
    SELECT uploader, domain
    FROM files
    WHERE filename = $1
    """,
        shortname,
    )

    if row is None:
        raise PrintException("file not found in db")

    uploader_id, domain_id = row["uploader"], row["domain"]

    if uploader_id == 0:
        raise PrintException("file is from dummy user")

    return domain_id


async def delete_file_cmd(args):
    shortname = args.shortname
    domain_id = await _extract_file_info(shortname)

    await app.db.execute(
        """
    UPDATE files
    SET deleted = true
    WHERE filename = $1
    """,
        shortname,
    )

    await app.storage.raw_invalidate(f"fspath:{domain_id}:{shortname}")

    print("OK", shortname)


async def undelete_file_cmd(args):
    shortname = args.shortname
    domain_id = await _extract_file_info(shortname)

    await app.db.execute(
        """
    UPDATE files
    SET deleted = false
    WHERE filename = $1
    """,
        shortname,
    )

    await app.storage.raw_invalidate(f"fspath:{domain_id}:{shortname}")

    print("OK", shortname)


async def nuke_file_cmd(args):
    shortname = args.shortname
    domain_id = await _extract_file_info(shortname)
    await delete_file(shortname, None, False)
    print("OK", shortname, "DOMAIN", domain_id)


def setup(subparsers):
    parser_cleanup = subparsers.add_parser(
        "cleanup_files",
        help="Delete files from the image folder",
        description="""
Delete all files that are marked as deleted in the image directory.
This is a legacy operation for instances that did not update
to a version of the backend that deletes files.
        """,
    )
    parser_cleanup.set_defaults(func=deletefiles)

    parser_rename = subparsers.add_parser("rename_file", help="Rename a single file")

    parser_rename.add_argument("shortname", help="old shortname for the file")
    parser_rename.add_argument("renamed", help="new shortname for the file")
    parser_rename.set_defaults(func=rename_file)

    parser_stats = subparsers.add_parser("stats", help="Statistics about the instance")

    parser_stats.set_defaults(func=show_stats)

    parser_del = subparsers.add_parser("delete", help="mark a file as deleted")

    parser_del.add_argument("shortname", help="shortname for the file to be deleted")
    parser_del.set_defaults(func=delete_file_cmd)

    parser_undel = subparsers.add_parser("undelete", help="mark a file as not deleted")

    parser_undel.add_argument(
        "shortname", help="shortname for the file to be undeleted"
    )
    parser_undel.set_defaults(func=undelete_file_cmd)

    parser_nuke = subparsers.add_parser(
        "nuke", help="delete a file, including filesystem"
    )

    parser_nuke.add_argument("shortname", help="shortname for the file to be nuked")
    parser_nuke.set_defaults(func=nuke_file_cmd)
