# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from typing import Dict, Union

from quart import current_app as app
from winter import get_snowflake

from api.common.auth import pwd_hash
from api.models import File
from api.errors import BadInput

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

    await app.db.execute(
        """
        INSERT INTO user_settings (user_id)
        VALUES ($1)
        """,
        user_id,
    )

    await app.redis.delete(f"uid:{username}")

    return {"user_id": user_id, "password_hash": password_hash}


async def full_file_delete(user_id: int, delete_user_after: bool = False):
    """Delete all the files from the user.

    Parameters
    ----------
    user_id: int
        User ID to have all files deleted from.
    delete_user, optional: bool
        If delete the user when all files are deleted
    """
    file_ids = await app.db.fetch(
        """
        SELECT file_id
        FROM files
        WHERE uploader = $1
          AND deleted = false
        """,
        user_id,
    )

    await File.delete_many(file_ids, user_id=user_id)
    log.info("delete user? %r", delete_user_after)

    if delete_user_after:
        log.info("Deleting user id %d", user_id)
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

    Raises ValueError if user_id is 0 (the doll user).

    Parameters
    ----------
    user_id: int
        User ID to delete.
    delete: bool, optional
        Delete the user records?
    """
    # instance admins should proceed to deleting the doll user via psql shell
    # if wanted.
    if user_id == 0:
        raise BadInput("doll user is not delete-able")

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
    return app.sched.spawn(
        full_file_delete, [user_id, delete], name=f"full_delete:{user_id}"
    )
