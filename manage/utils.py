# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import datetime

from quart import current_app as app
from api.models import User


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
    unix_timestamp = app.winter_factory.to_timestamp(user_id)
    timestamp = datetime.datetime.fromtimestamp(unix_timestamp)
    return datetime.datetime.utcnow() - timestamp
