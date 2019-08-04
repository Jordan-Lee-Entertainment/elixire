# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import secrets

from api.bp.profile import delete_user
from api.common.user import create_user
from api.common.auth import pwd_hash
from ..utils import get_user


async def adduser(_ctx, args):
    """Add a user."""
    email = args.email
    username = args.username

    password = args.password if args.password else secrets.token_urlsafe(25)

    if len(password) > 72:
        print("password is more than 72 characters, which is above bcrypt limitations")
        return

    udata = await create_user(username, password, email)

    print(
        f"""
    user id: {udata["user_id"]}
    username: {username!r}
    password: {password!r}
    """
    )


async def del_user(ctx, args):
    """Delete a user."""
    username = args.username
    userid = await get_user(ctx, username)

    task = await delete_user(userid, True)
    await asyncio.shield(task)

    print("OK")


async def resetpass(ctx, args):
    """Reset the password of the given user."""
    username = args.username
    user_id = await get_user(ctx, username)

    password = secrets.token_urlsafe(25)
    password_hash = await pwd_hash(password)

    dbout = await ctx.db.execute(
        """
        UPDATE users
        SET password_hash = $1
        WHERE user_id = $2
        """,
        password_hash,
        user_id,
    )

    # invalidate
    await ctx.redis.delete(f"uid:{user_id}:password_hash")
    await ctx.redis.delete(f"uid:{user_id}:active")

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
