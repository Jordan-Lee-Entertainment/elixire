# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import datetime

from quart import Quart, current_app as app
from winter import snowflake_time
from api.models import User


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
        app_ = Quart(__name__)
        app_.db = self.db
        app_.redis = self.redis
        app_.loop = self.loop
        app_.locks = self.locks
        app_.session = self.session
        app_.storage = self.storage
        app_.sched = self.sched
        app_.econfig = self.econfig
        return app_

    async def close(self):
        await self.db.close()
        self.redis.close()
        await self.redis.wait_closed()
        await self.session.close()


async def get_counts(user_id: int) -> str:
    """Show consent and count information in a string."""
    user = await User.fetch(user_id)

    assert user is not None
    consented = user.settings.consented

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


def account_delta(user_id: int) -> datetime.timedelta:
    """Show an account's age."""
    unix_timestamp = snowflake_time(user_id)
    timestamp = datetime.datetime.fromtimestamp(unix_timestamp)
    return datetime.datetime.utcnow() - timestamp
