# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from ..utils import get_user


async def unban_user(ctx, args):
    """Unban a single user"""
    username = args.username
    user_id = await get_user(ctx, username)
    await ctx.storage.invalidate(f"userban:{user_id}")

    exec_out = await ctx.db.execute(
        """
        DELETE FROM bans
        WHERE user_id = $1
        """,
        user_id,
    )

    print(f"SQL result: {exec_out}")


async def unban_ip(ctx, args):
    """Unban a single IP"""
    ipaddr = args.ipaddr
    await ctx.storage.invalidate(f"ipban:{ipaddr}")

    exec_out = await ctx.db.execute(
        """
        DELETE FROM ip_bans
        WHERE ip_address = $1
        """,
        ipaddr,
    )

    print(f"SQL result: {exec_out}")


def setup(subparser):
    parser_unban = subparser.add_parser(
        "unban_user",
        help="Unban a single user",
        description="""
This removes all current bans in the table.
        """,
    )

    parser_unban.add_argument("username")
    parser_unban.set_defaults(func=unban_user)

    parser_unban_ip = subparser.add_parser(
        "unban_ip",
        help="Unban a single IP",
        description="""
This removes all current IP bans in the table for the given IP.
        """,
    )

    parser_unban_ip.add_argument("ipaddr")
    parser_unban_ip.set_defaults(func=unban_ip)
