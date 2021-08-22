# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

# TODO: banip, unbanip
from ..utils import get_user


async def _invalidate(ctx, user_id: int):
    await ctx.storage.raw_invalidate(f"userban:{user_id}")


# TODO fix ban_user
async def ban_user(ctx, args):
    """Ban a single user."""
    username = args.username
    # interval = args.interval
    reason = args.reason
    user_id = await get_user(ctx, username)
    await _invalidate(ctx, user_id)

    print(
        await ctx.db.execute(
            """
            INSERT INTO bans (user_id, reason, end_timestamp)
            VALUES ($1, $2, $3)
            """,
            user_id,
            reason,
        )
    )


async def unban_user(ctx, args):
    """Unban a single user"""
    username = args.username
    user_id = await get_user(ctx, username)

    exec_out = await ctx.db.execute(
        """
    DELETE FROM bans
    WHERE user_id = $1
    """,
        user_id,
    )
    await _invalidate(ctx, user_id)

    print(f"SQL result: {exec_out}")


def setup(subparser):
    parser_ban = subparser.add_parser(
        "ban_user", aliases=["ban"], help="Ban a single user"
    )

    parser_ban.add_argument("username", help="The username to ban")
    parser_ban.add_argument("interval", help="How long to ban the user for")
    parser_ban.add_argument("reason", help="The ban reason")
    parser_ban.set_defaults(func=ban_user)

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
