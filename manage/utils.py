# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import datetime

from quart import Quart
from winter import snowflake_time
from .errors import ArgError


class Context:
    """manage.py's Context class.

    The Context class is the main class
    holding important information for integration
    of manage.py with current functions on
    the elixi.re codebase.

    Since the current functions take an app instance
    instead of a db connection instance, we pass Context
    instead of having to instantiate the sanic App object.
    """

    def __init__(self, econfig, db, redis, loop, locks):
        self.db = db
        self.redis = redis
        self.loop = loop
        self.locks = locks
        self.econfig = econfig

        # those are set later
        self.args = None
        self.session = None
        self.storage = None
        self.sched = None

    def make_app(self) -> Quart:
        app = Quart(__name__)
        app.db = self.db
        app.redis = self.redis
        app.loop = self.loop
        app.locks = self.locks
        app.session = self.session
        app.storage = self.storage
        app.sched = self.sched
        app.econfig = self.econfig
        return app


async def get_user(ctx: Context, username: str) -> int:
    """Fetch a user's ID, given username"""
    user_id = await ctx.db.fetchval(
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


async def get_counts(ctx: Context, user_id: int) -> str:
    """Show consent and count information in a string."""
    consented = await ctx.db.fetchval(
        """
        SELECT consented
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    files = await ctx.db.fetchval(
        """
        SELECT COUNT(*)
        FROM files
        WHERE files.uploader = $1
        """,
        user_id,
    )

    shortens = await ctx.db.fetchval(
        """
        SELECT COUNT(*)
        FROM files
        WHERE files.uploader = $1
        """,
        user_id,
    )

    cons = "consented" if consented else "not consented"
    return f"{cons}, {files} files, {shortens} shortens"


def account_delta(user_id: int) -> datetime.timedelta:
    """Show an account's age."""
    unix_timestamp = snowflake_time(user_id)
    timestamp = datetime.datetime.fromtimestamp(unix_timestamp)
    return datetime.datetime.utcnow() - timestamp
