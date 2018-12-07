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

# TODO: banip, unbanip
from ..utils import get_user


async def _invalidate(ctx, user_id: int):
    await ctx.storage.invalidate(f'userban:{user_id}')


async def ban_user(ctx, args):
    """Ban a single user."""
    username = args.username
    interval = args.interval
    reason = args.reason
    user_id = await get_user(ctx, username)
    await _invalidate(ctx, user_id)

    exec_out = await ctx.db.execute("""
    INSERT INTO bans (user_id, reason, end_timestamp)
    VALUES ($1, $2, $3)
    """, user_id, reason)

    print('AAA')


async def unban_user(ctx, args):
    """Unban a single user"""
    username = args.username
    user_id = await get_user(ctx, username)
    await _invalidate(ctx, user_id)

    exec_out = await ctx.db.execute("""
    DELETE FROM bans
    WHERE user_id = $1
    """, user_id)

    print(f'SQL result: {exec_out}')


def setup(subparser):
    parser_ban = subparser.add_parser('ban_user', aliases=['ban'],
                                      help='Ban a single user')

    parser_ban.add_argument('username', help='The username to ban')
    parser_ban.add_argument('interval', help='How long to ban the user for')
    parser_ban.add_argument('reason', help='The ban reason')
    parser_ban.set_defaults(func=ban_user)

    parser_unban = subparser.add_parser(
        'unban_user', help='Unban a single user', aliases=['unban'],
        description="""
This removes all current bans in the table.
        """)

    parser_unban.add_argument('username')
    parser_unban.set_defaults(func=unban_user)
