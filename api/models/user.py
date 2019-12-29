# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional
from quart import current_app as app


class User:
    """Represents an elixire user."""

    # TODO the rest
    __slots__ = ("id", "name", "email")

    def __init__(self, row):
        self.id: int = row["user_id"]
        self.name: str = row["username"]
        self.email: str = row["email"]

    def __eq__(self, other):
        return self.id == other.id

    @classmethod
    async def fetch(cls, user_id: int):
        raise NotImplementedError()

    @classmethod
    async def fetch_by(
        cls, *, username: str = None, email: str = None
    ) -> Optional["User"]:
        """Search a user by some uniquely identifieng field.

        Only one of the fields may be searched at a time.
        """

        assert username or email
        assert not (username and email)

        search_field = "username" if username else "email"

        value = username or email

        row = await app.db.fetchrow(
            f"""
            SELECT user_id, username, email
            FROM users
            WHERE search_field = $1
            LIMIT 1
            """,
            value,
        )

        return User(row) if row is not None else None
