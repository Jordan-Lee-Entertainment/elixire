# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional
from quart import current_app as app


class User:
    """Represents an elixire user."""

    __slots__ = (
        "id",
        "name",
        "active",
        "password_hash",
        "email",
        "consented",
        "admin",
        "paranoid",
        "subdomain",
        "domain",
        "shorten_subdomain",
        "shorten_domain",
    )

    def __init__(self, row):
        self.id: int = row["user_id"]
        self.name: str = row["username"]
        self.active: bool = row["active"]
        self.password_hash: str = row["password_hash"]
        self.email: str = row["email"]
        self.consented: Optional[bool] = row["consented"]
        self.admin: bool = row["admin"]
        self.paranoid: bool = row["paranoid"]

        self.domain: int = row["domain"]
        self.shorten_domain: Optional[int] = row["shorten_domain"]

        self.subdomain: str = row["subdomain"]
        self.shorten_subdomain: str = row["shorten_subdomain"]

    def __eq__(self, other):
        return self.id == other.id

    @classmethod
    async def fetch(cls, user_id: int) -> Optional["User"]:
        row = await app.db.fetchrow(
            f"""
            SELECT
                user_id, username, active, password_hash, email, consented,
                admin, paranoid, subdomain, domain, shorten_subdomain,
                shorten_domain
            FROM users
            WHERE user_id = $1
            LIMIT 1
            """,
            user_id,
        )

        return User(row) if row is not None else None

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
            SELECT
                user_id, username, active, password_hash, email, consented,
                admin, paranoid, subdomain, domain, shorten_subdomain,
                shorten_domain
            FROM users
            WHERE {search_field} = $1
            LIMIT 1
            """,
            value,
        )

        return User(row) if row is not None else None
