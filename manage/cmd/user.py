"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import asyncio
import secrets

import bcrypt

from api.snowflake import get_snowflake
from api.bp.profile import delete_user
from ..utils import get_user


async def adduser(ctx, args):
    """Add a user."""
    email = args.email
    username = args.username

    password = args.password if args.password else secrets.token_urlsafe(25)

    pass_hashing = password.encode()
    hashed = bcrypt.hashpw(pass_hashing, bcrypt.gensalt(14))

    user_id = get_snowflake()

    await ctx.db.execute("""
    INSERT INTO users (user_id, username, password_hash, email)
    VALUES ($1, $2, $3, $4)
    """, user_id, username, hashed.decode(), email)

    await ctx.db.execute("""
    INSERT INTO limits (user_id)
    VALUES ($1)
    """, user_id)

    await ctx.redis.delete(f'uid:{username}')

    print(f"""
    user id: {user_id}
    username: {username!r}
    password: {password!r}
    """)


async def del_user(ctx, args):
    """Delete a user."""
    username = args.username

    userid = await get_user(ctx, username)

    task = await delete_user(ctx, userid, True)
    await asyncio.shield(task)

    print('OK')


async def resetpass(ctx, args):
    username = args.username
    user_id = await get_user(ctx, username)
    password = secrets.token_urlsafe(25)

    _pwd = bytes(password, 'utf-8')
    hashed = bcrypt.hashpw(_pwd, bcrypt.gensalt(14))

    # insert on db
    dbout = await ctx.db.execute("""
    UPDATE users
    SET password_hash = $1
    WHERE user_id = $2
    """, hashed.decode('utf-8'), user_id)

    # invalidate
    await ctx.redis.delete(f'uid:{user_id}:password_hash')
    await ctx.redis.delete(f'uid:{user_id}:active')

    # print the user & password
    print(f"""
db out: {dbout}
username: {username!r}, {user_id!r}
new password: {password!r}
    """)


def setup(subparsers):
    parser_adduser = subparsers.add_parser(
        'adduser',
        help='Add a single user',
        description="""
The newly created user will be deactivated by default.
When password is not provided, a secure one is generated.
        """
    )
    parser_adduser.add_argument('email', help="User's email")
    parser_adduser.add_argument('username', help="User's new username")
    parser_adduser.add_argument('password', help='Password', nargs='?')
    parser_adduser.set_defaults(func=adduser)

    parser_del_user = subparsers.add_parser(
        'deluser',
        help='Delete a single user',
        description="""
This operation completly deletes all information on the user.

Please proceed with caution as there is no going back
from this operation.
        """
    )
    parser_del_user.add_argument('username',
                                 help='Username of the user to delete')
    parser_del_user.set_defaults(func=del_user)

    parser_resetpwd = subparsers.add_parser(
        'resetpass',
        help="Reset a user's password manually"
    )

    parser_resetpwd.add_argument('username',
                                 help='Username')

    parser_resetpwd.set_defaults(func=resetpass)
