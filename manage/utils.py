# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import datetime
from quart import current_app as app

from .errors import ArgError

from api.snowflake import snowflake_time


async def get_user(username: str) -> int:
    """Fetch a user's ID, given username"""
    user_id = await app.db.fetchval(
        """
    SELECT user_id
    FROM users
    WHERE username = $1
    """,
        username,
    )

    if not user_id:
        raise ArgError("no user found")

    return user_id


async def get_counts(user_id) -> str:
    """Show consent and count information in a string."""
    consented = await app.db.fetchval(
        """
    SELECT consented
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )

    files = await app.db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE files.uploader = $1
    """,
        user_id,
    )

    shortens = await app.db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE files.uploader = $1
    """,
        user_id,
    )

    cons = "consented" if consented else "not consented"

    return f"{cons}, {files} files, {shortens} shortens"


def account_delta(user_id) -> datetime.timedelta:
    """Show an account's age."""
    tstamp = snowflake_time(user_id)
    tstamp = datetime.datetime.fromtimestamp(tstamp)
    return datetime.datetime.utcnow() - tstamp
