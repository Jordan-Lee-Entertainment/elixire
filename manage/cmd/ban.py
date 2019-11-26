# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from ..utils import get_user
from api.common.banning import unban_user, unban_ip, TargetType, get_bans


async def unban_any(ctx, args):
    is_user = args.target_type == "user"

    unban_function = unban_user if is_user else unban_ip
    value = await get_user(ctx, args.target_value) if is_user else args.target_value

    await unban_function(value)
    print("OK")


async def getbans_cmd(ctx, args):
    is_user = args.target_type == "user"

    target_type = TargetType(args.target_type)
    value = await get_user(ctx, args.target_value) if is_user else args.target_value

    bans = await get_bans(value, target_type=target_type, page=args.page)

    print("page", args.page, ":")
    for ban in bans:
        print("\t", ban)


def setup(subparser):
    parser_unban = subparser.add_parser(
        "unban",
        help="Unban a user/IP",
        description="""
This removes all current bans in the table for the given target.
        """,
    )

    parser_unban.add_argument("target_type", choices=("user", "ip"))
    parser_unban.add_argument("target_value")
    parser_unban.set_defaults(func=unban_any)

    parser_getbans = subparser.add_parser("getbans", help="List the bans for a user/ip")

    # is it really target type?
    parser_getbans.add_argument("target_type", choices=("user", "ip"))
    parser_getbans.add_argument("target_value")
    parser_getbans.add_argument("page", nargs="?", default=0)

    parser_getbans.set_defaults(func=getbans_cmd)
