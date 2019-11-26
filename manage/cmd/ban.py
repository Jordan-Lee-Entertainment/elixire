# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from ..utils import get_user
from api.common.banning import unban_user, unban_ip


async def unban_user_cmd(ctx, args):
    """Unban a single user"""
    user_id = await get_user(ctx, args.username)
    await unban_user(user_id)
    print("OK")


async def unban_ip_cmd(_ctx, args):
    """Unban a single IP"""
    await unban_ip(args.ipaddr)
    print("OK")


def setup(subparser):
    parser_unban = subparser.add_parser(
        "unban_user",
        help="Unban a single user",
        description="""
This removes all current bans in the table.
        """,
    )

    parser_unban.add_argument("username")
    parser_unban.set_defaults(func=unban_user_cmd)

    parser_unban_ip = subparser.add_parser(
        "unban_ip",
        help="Unban a single IP",
        description="""
This removes all current IP bans in the table for the given IP.
        """,
    )

    parser_unban_ip.add_argument("ipaddr")
    parser_unban_ip.set_defaults(func=unban_ip_cmd)
