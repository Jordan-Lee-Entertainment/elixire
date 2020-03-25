# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Tuple, Union
from api.models import User
from api.common.banning import unban_user, unban_ip, TargetType, get_bans


async def _extract_ban_actor(args) -> Tuple[TargetType, Union[str, int]]:
    target_type = TargetType(args.target_type)
    value = args.target_value

    if target_type == TargetType.User:
        user = await User.fetch_by(username=args.target_value)
        assert user is not None
        value = user.id

    return target_type, value


async def unban_any(ctx, args):
    target_type, value = await _extract_ban_actor(args)

    unban_function = unban_user if target_type == TargetType.User else unban_ip
    await unban_function(value)
    print("OK")


async def getbans_cmd(ctx, args):
    target_type, value = await _extract_ban_actor(args)

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

    parser_getbans.add_argument("target_type", choices=("user", "ip"))
    parser_getbans.add_argument("target_value")
    parser_getbans.add_argument("page", nargs="?", default=0)

    parser_getbans.set_defaults(func=getbans_cmd)
