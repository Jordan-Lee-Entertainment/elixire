# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any
from quart import current_app as app


class User:
    """Represents an elixire user."""

    __slots__ = (
        "id",
        "name",
        "active",
        "email",
        "consented",
        "admin",
        "paranoid",
        "subdomain",
        "domain",
        "shorten_subdomain",
        "shorten_domain",
        "file_byte_limit",
        "shorten_limit",
    )

    def __init__(self, row):
        self.id: int = row["user_id"]
        self.name: str = row["username"]
        self.active: bool = row["active"]
        # self.password_hash: str = row["password_hash"]
        self.email: str = row["email"]
        self.consented: Optional[bool] = row["consented"]
        self.admin: bool = row["admin"]
        self.paranoid: bool = row["paranoid"]

        self.domain: int = row["domain"]
        self.shorten_domain: Optional[int] = row["shorten_domain"]

        self.subdomain: str = row["subdomain"]
        self.shorten_subdomain: str = row["shorten_subdomain"]

        self.file_byte_limit: int = row["file_byte_limit"]
        self.shorten_limit: int = row["shorten_limit"]

    def __eq__(self, other):
        return self.id == other.id

    @classmethod
    async def fetch(cls, user_id: int) -> Optional["User"]:
        row = await app.db.fetchrow(
            f"""
            SELECT
                users.user_id, username, active, email, consented,
                admin, paranoid, subdomain, domain, shorten_subdomain,
                shorten_domain, blimit AS file_byte_limit, shlimit AS shorten_limit
            FROM users
            JOIN limits
            ON users.user_id = limits.user_id
            WHERE users.user_id = $1
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
                users.user_id, username, active, email, consented,
                admin, paranoid, subdomain, domain, shorten_subdomain,
                shorten_domain, blimit AS file_byte_limit, shlimit AS shorten_limit
            FROM users
            JOIN limits
            ON users.user_id = limits.user_id
            WHERE {search_field} = $1
            LIMIT 1
            """,
            value,
        )

        return User(row) if row is not None else None

    def to_dict(self) -> Dict[str, Any]:
        """Get the user as a dictionary."""
        user_dict: Dict[str, Any] = {}
        for field in User.__slots__:
            user_dict[field] = getattr(self, field)

        return user_dict
