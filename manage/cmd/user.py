# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import secrets

from quart import current_app as app

from api.bp.profile import delete_user
from api.common.user import create_user
from api.common.auth import pwd_hash
from api.common.email import send_email_to_user
from api.models import User


async def adduser(args):
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


async def del_user(args):
    """Delete a user."""
    user = await User.fetch_by(username=args.username)
    assert user is not None

    task = await delete_user(user.id, True)
    await asyncio.shield(task)

    print("OK")


async def resetpass(args):
    """Reset the password of the given user."""
    user = await User.fetch_by(username=args.username)
    assert user is not None

    password = secrets.token_urlsafe(25)
    password_hash = await pwd_hash(password)

    dbout = await app.db.execute(
        """
        UPDATE users
        SET password_hash = $1
        WHERE user_id = $2
        """,
        password_hash,
        user.id,
    )

    # invalidate
    await app.redis.delete(f"uid:{user.id}:password_hash")
    await app.redis.delete(f"uid:{user.id}:active")

    # print the user & password
    print(
        f"""
db out: {dbout}
username: {user.name!r}, {user.id!r}
new password: {password!r}
    """
    )


async def sendmail(args):
    """Send email to a user"""
    user = await User.fetch_by(username=args.username)
    assert user is not None

    body = "\n".join(args.body)
    user_email = await send_email_to_user(user.id, args.subject, body)
    print("OK", user_email)


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

    parser_sendmail = subparsers.add_parser("sendmail", help="Send an email to a user")
    parser_sendmail.add_argument("username", help="Username")
    parser_sendmail.add_argument("subject", help="Email subject")
    parser_sendmail.add_argument("body", help="Email body", nargs="+")
    parser_sendmail.set_defaults(func=sendmail)
