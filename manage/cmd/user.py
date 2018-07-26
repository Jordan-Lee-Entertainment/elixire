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

