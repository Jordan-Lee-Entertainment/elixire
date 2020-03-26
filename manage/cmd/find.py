# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import current_app as app
from ..utils import account_delta, get_counts


async def find_inactive_users(args):
    """Find inactive users.

    The criteria for inactive users are accounts
    that are deactivated AND are older than 2 weeks.
    """
    uids = await app.db.fetch(
        """
        SELECT username, user_id
        FROM users
        WHERE users.active = false
        AND now() - snowflake_time(user_id) > interval '2 weeks'
        """
    )

    for row in uids:
        delta = account_delta(row["user_id"])
        cinfo = await get_counts(row["user_id"])
        print(f'\t- {row["username"]} {row["user_id"]}, ' f"{cinfo}, created {delta}")

    print(f"{len(uids)} users were found")


async def find_unused_accs(_args):
    """Find unused accounts.

    The criteria for unused accounts are users
    that have no files for a month.
    """

    users = await app.db.fetch(
        """
        SELECT username, user_id
        FROM users
        """
    )

    count = 0

    for row in users:
        uid = row["user_id"]

        inactive = await app.db.fetchval(
            """
            SELECT (now() - snowflake_time(MAX(file_id))) > interval '1 month'
            FROM files
            WHERE files.uploader = $1
            """,
            uid,
        )

        if not inactive:
            continue

        delta = account_delta(row["user_id"])
        counts = await get_counts(row["user_id"])
        print(f'\t- {row["username"]} {row["user_id"]}, ' f"{counts}, created {delta}")
        count += 1

    print(f"{count} unused accounts were found")


def setup(subparsers):
    parser_inactive = subparsers.add_parser(
        "find_inactive",
        help="Find inactive accounts",
        description="""
The criteria for inactive accounts are ones that are:
 - deactivated
 - older than two weeks
        """,
    )

    parser_inactive.set_defaults(func=find_inactive_users)

    parser_unused = subparsers.add_parser(
        "find_unused",
        help="Find unused accounts",
        description="""
The criteria for unused accounts are users
who didn't have any files uploaded in a month.
        """,
    )

    parser_unused.set_defaults(func=find_unused_accs)
