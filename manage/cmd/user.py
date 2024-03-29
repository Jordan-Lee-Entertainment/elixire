# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import secrets

import bcrypt

from api.snowflake import get_snowflake
from api.bp.profile import delete_user
from quart import current_app as app
from ..utils import get_user


async def adduser(args):
    """Add a user."""
    email = args.email
    username = args.username

    password = args.password if args.password else secrets.token_urlsafe(25)

    pass_hashing = password.encode()
    hashed = bcrypt.hashpw(pass_hashing, bcrypt.gensalt(14))

    user_id = get_snowflake()

    await app.db.execute(
        """
    INSERT INTO users (user_id, username, password_hash, email)
    VALUES ($1, $2, $3, $4)
    """,
        user_id,
        username,
        hashed.decode(),
        email,
    )

    await app.db.execute(
        """
    INSERT INTO limits (user_id)
    VALUES ($1)
    """,
        user_id,
    )

    await app.redis.delete(f"uid:{username}")

    print(
        f"""
    user id: {user_id}
    username: {username!r}
    password: {password!r}
    """
    )


async def del_user(args):
    """Delete a user."""
    username = args.username

    userid = await get_user(username)

    task = await delete_user(userid, True)
    await asyncio.shield(task)

    print("OK")


async def resetpass(args):
    username = args.username
    user_id = await get_user(username)
    password = secrets.token_urlsafe(25)

    _pwd = bytes(password, "utf-8")
    hashed = bcrypt.hashpw(_pwd, bcrypt.gensalt(14))

    # insert on db
    dbout = await app.db.execute(
        """
    UPDATE users
    SET password_hash = $1
    WHERE user_id = $2
    """,
        hashed.decode("utf-8"),
        user_id,
    )

    # invalidate
    await app.redis.delete(f"uid:{user_id}:password_hash")
    await app.redis.delete(f"uid:{user_id}:active")

    # print the user & password
    print(
        f"""
db out: {dbout}
username: {username!r}, {user_id!r}
new password: {password!r}
    """
    )


def setup(subparsers):
    parser_adduser = subparsers.add_parser(
        "adduser",
        help="Add a single user",
        description="""
The newly created user will be deactivated by default.
When password is not provided, a secure one is generated.
        """,
    )
    parser_adduser.add_argument("email", help="User's email")
    parser_adduser.add_argument("username", help="User's new username")
    parser_adduser.add_argument("password", help="Password", nargs="?")
    parser_adduser.set_defaults(func=adduser)

    parser_del_user = subparsers.add_parser(
        "deluser",
        help="Delete a single user",
        description="""
This operation completly deletes all information on the user.

Please proceed with caution as there is no going back
from this operation.
        """,
    )
    parser_del_user.add_argument("username", help="Username of the user to delete")
    parser_del_user.set_defaults(func=del_user)

    parser_resetpwd = subparsers.add_parser(
        "resetpass", help="Reset a user's password manually"
    )

    parser_resetpwd.add_argument("username", help="Username")

    parser_resetpwd.set_defaults(func=resetpass)
