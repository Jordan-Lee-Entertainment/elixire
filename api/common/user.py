# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
import asyncio
from typing import Dict, Union, Any, Optional

from quart import current_app as app

from api.common.auth import pwd_hash
from api.snowflake import get_snowflake
from api.common import delete_file

log = logging.getLogger(__name__)


async def create_user(
    username: str, password: str, email: str, *, active: bool = True
) -> Dict[str, Union[str, int]]:
    """Creates a single user. Outputs a dictionary containing the user's
    newly generated ID and password hash."""
    user_id = get_snowflake()
    password_hash = await pwd_hash(password)

    await app.db.execute(
        """
        INSERT INTO users (user_id, username, password_hash, email, active)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id,
        username,
        password_hash,
        email,
        active,
    )

    await app.db.execute(
        """
        INSERT INTO limits (user_id)
        VALUES ($1)
        """,
        user_id,
    )

    await app.redis.delete(f"uid:{username}")

    return {"user_id": user_id, "password_hash": password_hash}


async def _delete_file_wrapper(shortname, user_id):
    """Wrapper function for a single file delete, so that users doing
    multiple deletes don't run into concurrency problems.

    This function requires a lock due to the extra work delete_file()
    goes through, creating dummy users, checking external fspaths, etc.
    """
    lock = app.locks["delete_files"][user_id]
    async with lock:
        await delete_file(shortname, user_id, False)


async def mass_file_delete(user_id: int, delete=False):
    """Delete all the files from the user.

    Parameters
    ----------
    user_id: int
        User ID to have all files deleted from.
    delete, optional: bool
        If delete the user when all files are deleted
    """
    file_shortnames = await app.db.fetch(
        """
        SELECT filename
        FROM files
        WHERE uploader = $1
        """,
        user_id,
    )

    log.info(f"Deleting ALL {len(file_shortnames)} files")

    tasks = []

    for row in file_shortnames:
        shortname = row["filename"]
        task = app.sched.spawn(
            _delete_file_wrapper(shortname, user_id), name=f"_del_wrapper_{shortname}"
        )
        tasks.append(task)

    if tasks:
        await asyncio.wait(tasks)

    log.info(f"finished waiting for {len(tasks)} tasks")
    log.info(f"delete? {delete}")

    if delete:
        log.info(f"Deleting user id {user_id}")
        await app.db.execute(
            """
            DELETE FROM users
            WHERE user_id = $1
            """,
            user_id,
        )


async def delete_user(user_id: int, delete: bool = False):
    """Delete all user files.

    If the delete flag is set, it will delete the user record,
    else it'll mark the user as deactivated.

    Parameters
    ----------
    user_id: int
        User ID to delete.
    delete: bool, optional
        Delete the user records?
    """
    # ignore deletion of the dummy user via any admin-facing
    # administration util (manage.py will also be unable
    # to delete the dummy user).
    #  instance admins should proceed to deleting via the psql shell.
    if user_id == 0:
        log.warning("Not deleting dummy user")
        return

    await app.db.execute(
        """
        UPDATE users
        SET active = false
        WHERE user_id = $1
        """,
        user_id,
    )

    await app.db.execute(
        """
        UPDATE files
        SET deleted = true
        WHERE uploader = $1
        """,
        user_id,
    )

    await app.db.execute(
        """
        UPDATE shortens
        SET deleted = true
        WHERE uploader = $1
        """,
        user_id,
    )

    await app.storage.invalidate(user_id, "active", "password_hash")

    # since there is a lot of db load
    # when calling delete_file, we create a task that deletes them.

    return app.sched.spawn(mass_file_delete(user_id, delete), f"delete_files_{user_id}")


# TODO better typing
async def get_basic_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get a basic user dictionary from the users table."""
    user = await app.db.fetchrow(
        """
        SELECT user_id::text, username, active, email,
            consented, admin, subdomain, domain, paranoid,
            shorten_domain, shorten_subdomain
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    if user is None:
        return None

    return dict(user)
