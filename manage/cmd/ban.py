# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from ..utils import get_user


async def _invalidate(ctx, user_id: int):
    await ctx.storage.invalidate(f"userban:{user_id}")


async def unban_user(ctx, args):
    """Unban a single user"""
    username = args.username
    user_id = await get_user(ctx, username)
    await _invalidate(ctx, user_id)

    exec_out = await ctx.db.execute(
        """
        DELETE FROM bans
        WHERE user_id = $1
        """,
        user_id,
    )

    print(f"SQL result: {exec_out}")


def setup(subparser):
    parser_unban = subparser.add_parser(
        "unban_user",
        help="Unban a single user",
        aliases=["unban"],
        description="""
This removes all current bans in the table.
        """,
    )

    parser_unban.add_argument("username")
    parser_unban.set_defaults(func=unban_user)
