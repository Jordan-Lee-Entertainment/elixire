"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import datetime

from .errors import ArgError

from api.snowflake import snowflake_time


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
    def __init__(self, db, redis, loop, locks):
        self.db = db
        self.redis = redis
        self.loop = loop
        self.locks = locks

        # those are set later
        self.args = None
        self.session = None
        self.storage = None
        self.sched = None


async def get_user(ctx, username: str) -> int:
    """Fetch a user's ID, given username"""
    user_id = await ctx.db.fetchval("""
    SELECT user_id
    FROM users
    WHERE username = $1
    """, username)

    if not user_id:
        raise ArgError('no user found')

    return user_id


async def get_counts(ctx, user_id) -> str:
    """Show consent and count information in a string."""
    consented = await ctx.db.fetchval("""
    SELECT consented
    FROM users
    WHERE user_id = $1
    """, user_id)

    files = await ctx.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE files.uploader = $1
    """, user_id)

    shortens = await ctx.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    WHERE files.uploader = $1
    """, user_id)

    cons = 'consented' if consented else 'not consented'

    return f'{cons}, {files} files, {shortens} shortens'


def account_delta(user_id) -> datetime.timedelta:
    """Show an account's age."""
    tstamp = snowflake_time(user_id)
    tstamp = datetime.datetime.fromtimestamp(tstamp)
    return datetime.datetime.utcnow() - tstamp
