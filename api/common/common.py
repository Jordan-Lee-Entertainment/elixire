# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import string
import secrets
import hashlib
import logging
import time
from pathlib import Path
from typing import Tuple

import asyncpg
from quart import current_app as app, request

from ..errors import FailedAuth, NotFound

ALPHABET = string.ascii_lowercase + string.digits
log = logging.getLogger(__name__)


class TokenType:
    """Token type "enum"."""
    NONTIMED = 1
    TIMED = 2


class FileNameType:
    """Represents a type of a filename."""
    FILE = 0
    SHORTEN = 1


def get_ip_addr(request) -> str:
    """Fetch the IP address for a request.

    Handles the cloudflare headers responsible to set
    the client's IP.
    """
    if 'X-Forwarded-For' not in request.headers:
        return request.remote_addr
    return request.headers['X-Forwarded-For']


def _gen_fname(length) -> str:
    """Generate a random filename."""
    return ''.join(secrets.choice(ALPHABET)
                   for _ in range(length))


async def gen_filename(length=3, table='files',
                       _curc=0) -> Tuple[str, int]:
    """Generate a unique random filename.

    To guarantee that the generated shortnames will
    be unique, we query our DB if the generated
    shortname already exists, and retry if it does.

    Parameters
    ----------
    request: sanic.Request
        So the function can call the database.

    length, optional: int
        Minimal amount of characters to use, default 3.
        Grows with the amount of failed generations.

    table, optional: str
        The table to generate a unique shortname for,
        by default being the 'files' table.

    Returns
    -------
    tuple
        Containing the generated shortname
        and how many tries happened to generate it.

    Raises
    ------
    RuntimeError
        If it tried to generate a shortname with more than 10 letters.
    """
    if length > 10:
        raise RuntimeError('Failed to generate a filename')

    try_count = 0

    field = 'file_id' if table == 'files' else 'shorten_id'

    for try_count in range(10):
        random_fname = _gen_fname(length)

        filerow = await request.app.db.fetchrow(f"""
        SELECT {field}
        FROM {table}
        WHERE filename = $1
        """, random_fname)

        if not filerow:
            total = _curc + try_count
            log.info(f'Took {total} retries to '
                     f'generate {random_fname!r}')
            return random_fname, total

    # if 10 tries didnt work, try generating with length+1
    return await gen_filename(length + 1, table,
                              _curc + try_count + 1)


def _calculate_hash(fhandler) -> str:
    """Generate a hash of the given file.

    This calls the seek(0) of the file handler
    so it can be reused.

    Parameters
    ----------
    fhandler: file object
        Any file-like object.

    Returns
    -------
    str
        The SHA256 hash of the given file.
    """
    hashstart = time.monotonic()
    hash_obj = hashlib.sha256()

    for chunk in iter(lambda: fhandler.read(4096), b""):
        hash_obj.update(chunk)

    # so that we can reuse the same handler
    # later on
    fhandler.seek(0)

    hashend = time.monotonic()
    delta = round(hashend - hashstart, 6)
    log.info(f'Hashing file took {delta} seconds')

    return hash_obj.hexdigest()


async def calculate_hash(fhandle) -> str:
    """Calculate a hash of the given file handle.

    Uses run_in_executor to do the job asynchronously so
    the application doesn't lock up on large files.
    """
    fut = app.loop.run_in_executor(None, _calculate_hash, fhandle)
    return await fut


async def remove_fspath(shortname: str):
    """Delete the given file shortname from the database.

    Checks if any other files are sharing fspath, and if there are none,
    the underlying fspath is deleted.
    """
    if shortname is None:
        return

    fspath = await app.db.fetchval("""
    SELECT fspath
    FROM files
    WHERE filename = $1
    """, shortname)

    if fspath is None:
        return

    # fetch all files with the same fspath
    # and on the hash system, means the same hash
    same_fspath = await app.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE fspath = $1 AND deleted = false
    """, fspath)

    if same_fspath == 0:
        path = Path(fspath)
        try:
            path.unlink()
            log.info(f'Deleted {fspath!s} since no files refer to it')
        except FileNotFoundError:
            log.warning(f'fspath {fspath!s} does not exist')
    else:
        log.info(f'there are still {same_fspath} files with the '
                 f'same fspath {fspath!s}, not deleting')


async def delete_file(file_name: str, user_id, set_delete=True):
    """Delete a file, purging it from Cloudflare's cache.

    Parameters
    ----------
    file_name: str
        File shortname to be deleted.
    user_id: int
        User ID making the request, so we
        crosscheck that information with the file's uploader.
    set_delete, optional: bool
        If we set the deleted field to true OR
        delete the row directly.

    Raises
    ------
    NotFound
        If no file is found.
    """
    domain_id = await app.storage.get_domain_file(file_name)

    try:
        await app.db.execute("""
        INSERT INTO users (user_id, username, active, password_hash, email)
        VALUES (0, 'dummy', false, 'blah', 'd u m m y')
        """)
    except asyncpg.UniqueViolationError:
        pass

    if set_delete:
        exec_out = await app.db.execute("""
        UPDATE files
        SET deleted = true
        WHERE uploader = $1
          AND filename = $2
          AND deleted = false
        """, user_id, file_name)

        if exec_out == "UPDATE 0":
            raise NotFound('You have no files with this name.')

        await remove_fspath(file_name)
    else:
        await remove_fspath(file_name)

        if user_id:
            await app.db.execute("""
            UPDATE files
            SET uploader = 0,
                file_size = 0,
                fspath = '',
                deleted = true,
                domain = 0
            WHERE
                filename = $1
            AND uploader = $2
            """, file_name, user_id)
        else:
            await app.db.execute("""
            UPDATE files
            SET uploader = 0,
                file_size = 0,
                fspath = '',
                deleted = true,
                domain = 0
            WHERE filename = $1
            """, file_name)

    await app.storage.raw_invalidate(f'fspath:{domain_id}:{file_name}')


async def delete_shorten(shortname: str, user_id: int):
    """Remove a shorten from the system"""
    exec_out = await app.db.execute("""
    UPDATE shortens
    SET deleted = true
    WHERE uploader = $1
    AND filename = $2
    AND deleted = false
    """, user_id, shortname)

    # By doing this, we're cutting down DB calls by half
    # and it still checks for user
    if exec_out == "UPDATE 0":
        raise NotFound('You have no shortens with this name.')

    domain_id = await app.storage.get_domain_shorten(shortname)
    await app.storage.raw_invalidate(f'redir:{domain_id}:{shortname}')


async def check_bans(user_id: int):
    """Check if the current user is already banned.

    Raises
    ------
    FailedAuth
        When a user is banned, or their
        IP address is banned.
    """
    if user_id is not None:
        reason = await app.storage.get_ban(user_id)

        if reason:
            raise FailedAuth(f'User is banned. {reason}')

    ip_addr = get_ip_addr(request)
    ip_ban_reason = await app.storage.get_ipban(ip_addr)
    if ip_ban_reason:
        raise FailedAuth(f'IP address is banned. {ip_ban_reason}')


async def get_domain_info(user_id: int,
                          dtype=FileNameType.FILE) -> Tuple[int, str, str]:
    """Get information about a user's selected domain.

    Parameters
    ----------
    request: sanic.Request
        Request object for database access.
    user_id: int
        User's snowflake ID.
    dtype, optional: FileNameType
        What type of domain to get? (file or shorten).
        Defaults to file.

    Returns
    -------
    tuple
        with 3 values: domain id, subdomain and the domain string
    """
    domain_id, subdomain_name = await app.db.fetchrow("""
    SELECT domain, subdomain
    FROM users
    WHERE user_id = $1
    """, user_id)

    domain = await app.db.fetchval("""
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    if dtype == FileNameType.SHORTEN:
        shorten_domain_id, shorten_subdomain = await app.db.fetchrow("""
        SELECT shorten_domain, shorten_subdomain
        FROM users
        WHERE user_id = $1
        """, user_id)

        if shorten_domain_id is not None:
            shorten_domain = await app.db.fetchval("""
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """, shorten_domain_id)

            # if we have all the data on shorten subdomain, return it
            return shorten_domain_id, shorten_subdomain, shorten_domain

    return domain_id, subdomain_name, domain


async def get_random_domain() -> int:
    """Get a random domain from the table."""
    return await app.db.fetchval("""
    SELECT domain_id FROM domains
    ORDER BY RANDOM()
    LIMIT 1
    """)


def transform_wildcard(domain: str, subdomain_name: str) -> str:
    """Do domain transformations in the case of a wildcard.

    Parameters
    ---------
    domain: str
        The domain as a template for the transformation.
    subdomain_name: str
        The subdomain to be applied on the template.

    Returns
    -------
    str
        The actual domain you should use.
    """
    # Check if it's wildcard and if we have a subdomain set
    if domain[0:2] == '*.':
        if subdomain_name:
            domain = domain.replace("*.", f"{subdomain_name}.")
        else:
            domain = domain.replace("*.", "")

    return domain
