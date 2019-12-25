# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import string
import secrets
import hashlib
import logging
import time
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Union

from quart import current_app as app, request

from api.errors import FailedAuth, NotFound
from api.storage import object_key

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


def get_ip_addr() -> str:
    """Fetch the IP address for a request.

    Handles the cloudflare headers responsible to set
    the client's IP.
    """
    if "X-Forwarded-For" not in request.headers:
        return request.remote_addr
    return request.headers["X-Forwarded-For"]


def _gen_sname(length: int) -> str:
    """Generate a random shortname."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


async def gen_shortname(
    length: int = 3, table: str = "files", _curc: int = 0
) -> Tuple[str, int]:
    """Generate a unique random shortname.

    To guarantee that the generated shortnames will
    be unique, we query our DB if the generated
    shortname already exists, and retry if it does.

    Parameters
    ----------
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
        raise RuntimeError("Failed to generate a shortname")

    try_count = 0

    field = "file_id" if table == "files" else "shorten_id"

    for try_count in range(10):
        random_fname = _gen_sname(length)

        filerow = await app.db.fetchrow(
            f"""
            SELECT {field}
            FROM {table}
            WHERE filename = $1
            """,
            random_fname,
        )

        if not filerow:
            total = _curc + try_count
            log.info(f"Took {total} retries to " f"generate {random_fname!r}")
            return random_fname, total

    # if 10 tries didnt work, try generating with length+1
    return await gen_shortname(length + 1, table, _curc + try_count + 1)


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
    log.info(f"Hashing file took {delta} seconds")

    return hash_obj.hexdigest()


async def calculate_hash(fhandle) -> str:
    """Calculate a hash of the given file handle.

    Uses run_in_executor to do the job asynchronously so
    the application doesn't lock up on large files.
    """
    return await app.loop.run_in_executor(None, _calculate_hash, fhandle)


async def remove_fspath(file_id: Optional[int]) -> None:
    """Delete the given file shortname from the database.

    Checks if any other files are sharing fspath, and if there are none,
    the underlying fspath is deleted.
    """
    if file_id is None:
        return

    # fetch all files with the same fspath
    # and on the hash system, means the same hash
    row = await app.db.fetchrow(
        """
        SELECT fspath, COUNT(*)
        FROM files
        WHERE fspath = (SELECT fspath FROM files WHERE file_id = $1)
          AND deleted = false
        GROUP BY fspath
        """,
        file_id,
    )

    if row is None:
        return

    fspath, same_fspath = row["fspath"], row["count"]

    if same_fspath != 0:
        log.info(
            "there are still %d files with the same fspath %r, not deleting",
            same_fspath,
            fspath,
        )
        return

    path = Path(fspath)
    try:
        path.unlink()
        log.info("Deleted %r since no files refer to it", fspath)
    except FileNotFoundError:
        log.warning("fspath %s does not exist", fspath)


async def delete_file(
    user_id: Optional[int] = None,
    *,
    by_name: Optional[str] = None,
    by_id: Optional[int] = None,
    full_delete: bool = False,
):
    """Delete a file.

    Parameters
    ----------
    user_id: int
        User ID making the request, so we
        crosscheck that information with the file's uploader.
    full_delete, optional: bool
        Move the ownership of the file to the doll user.

    Raises
    ------
    NotFound
        If no file is found.
    """

    column = "file_id" if by_id is not None else "filename"
    selector = by_id or by_name

    if not full_delete:
        row = await app.db.fetchrow(
            f"""
            UPDATE files
            SET deleted = true
            WHERE uploader = $1
            AND {column} = $2
            AND deleted = false
            RETURNING domain, subdomain, file_id, filename
            """,
            user_id,
            selector,
        )

        if row is None:
            raise NotFound("You have no files with this name.")

        await remove_fspath(row["file_id"])
    else:
        uploader = "AND uploader = $2" if user_id else ""

        row = await app.db.fetchrow(
            f"""
            UPDATE files
            SET uploader = 0,
                file_size = 0,
                fspath = '',
                deleted = true,
                domain = 0
            WHERE
                {column} = $1
                {uploader}
            RETURNING domain, subdomain, file_id, filename
            """,
            selector,
            *([user_id] if user_id else []),
        )

        await remove_fspath(row["file_id"])

    await app.storage.raw_invalidate(
        object_key("fspath", row["domain"], row["subdomain"], row["filename"])
    )


async def delete_shorten(
    user_id: int, *, by_name: Optional[str] = None, by_id: Optional[int] = None
):
    """Delete a shorten."""
    if by_id and by_name:
        raise ValueError("Please elect either ID or name to delete")

    column = "shorten_id" if by_id is not None else "filename"
    # TODO set redirto to empty string?
    row = await app.db.fetchrow(
        f"""
        UPDATE shortens
        SET deleted = true
        WHERE uploader = $1
          AND {column} = $2
          AND deleted = false
        RETURNING domain, subdomain, filename
        """,
        user_id,
        by_id or by_name,
    )

    if row is None:
        raise NotFound("You have no shortens with this name.")

    await app.storage.raw_invalidate(
        object_key("redir", row["domain"], row["subdomain"], row["filename"])
    )


async def delete_file_user_lock(user_id: Optional[int], file_id: int):
    lock = app.locks["delete_files"][user_id]
    async with lock:
        await delete_file(user_id, by_id=file_id, full_delete=True)


async def delete_many(file_ids: List[int], *, user_id: Optional[int] = None):
    tasks = []

    for file_id in file_ids:
        task = app.sched.spawn(
            delete_file_user_lock, [user_id, file_id], job_id=f"delete_file:{file_id}",
        )
        tasks.append(task)

    if not tasks:
        log.warning("no tasks")
        return

    log.info("waiting for %d file tasks", len(tasks))
    done, pending = await asyncio.wait(tasks)
    log.info(
        "waited for %d file tasks, %d done, %d pending",
        len(tasks),
        len(done),
        len(pending),
    )
    assert not pending
    for task in done:
        try:
            task.result()
        except Exception:
            log.exception("exception while deleting file")


async def check_bans(user_id: Optional[int] = None):
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
            raise FailedAuth(f"User is banned. {reason}")

    ip_addr = get_ip_addr()
    ip_ban_reason = await app.storage.get_ipban(ip_addr)
    if ip_ban_reason:
        raise FailedAuth(f"IP address is banned. {ip_ban_reason}")


async def get_user_domain_info(
    user_id: int, dtype=FileNameType.FILE
) -> Tuple[int, str, str]:
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
    domain_id, subdomain_name = await app.db.fetchrow(
        """
        SELECT domain, subdomain
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    domain = await app.db.fetchval(
        """
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    if dtype == FileNameType.SHORTEN:
        shorten_domain_id, shorten_subdomain = await app.db.fetchrow(
            """
            SELECT shorten_domain, shorten_subdomain
            FROM users
            WHERE user_id = $1
            """,
            user_id,
        )

        if shorten_domain_id is not None:
            shorten_domain = await app.db.fetchval(
                """
                SELECT domain
                FROM domains
                WHERE domain_id = $1
                """,
                shorten_domain_id,
            )

            # if we have all the data on shorten subdomain, return it
            return shorten_domain_id, shorten_subdomain, shorten_domain

    return domain_id, subdomain_name, domain


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
    if domain[0:2] == "*.":
        if subdomain_name:
            domain = domain.replace("*.", f"{subdomain_name}.")
        else:
            domain = domain.replace("*.", "")

    return domain


async def get_tags() -> List[Dict[str, Union[int, str]]]:
    """Get a mapping from tag ID to tag label."""
    tag_rows = await app.db.fetch(
        "SELECT tag_id, label FROM domain_tags ORDER BY tag_id ASC"
    )
    return [{"id": r["tag_id"], "label": r["label"]} for r in tag_rows]
