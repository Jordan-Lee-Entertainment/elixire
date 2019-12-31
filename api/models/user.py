# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any
from quart import current_app as app


async def _get_uploaded_count_from(
    user_id: int, *, table: str, extra_sql: str = ""
) -> int:
    return (
        await app.db.fetchval(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE uploader = $1
            {extra_sql}
            """,
            user_id,
        )
        or 0
    )


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
    )

    def __init__(self, row) -> None:
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

    def __eq__(self, other) -> bool:
        return self.id == other.id

    @classmethod
    async def fetch(cls, user_id: int) -> Optional["User"]:
        row = await app.db.fetchrow(
            f"""
            SELECT
                user_id, username, active, email, consented,
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
        """Fetch a user by some uniquely identifying field.

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
                shorten_domain
            FROM users
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

    async def fetch_limits(self) -> Dict[str, int]:
        """Fetch the limits and used resources of the user."""
        limits = await app.db.fetchrow(
            """
            SELECT blimit, shlimit
            FROM limits
            WHERE user_id = $1
            """,
            self.id,
        )
        assert limits is not None

        bytes_used = await app.db.fetchval(
            """
            SELECT SUM(file_size)
            FROM files
            WHERE uploader = $1
            AND file_id > time_snowflake(now() - interval '7 days')
            """,
            self.id,
        )

        shortens_used = await app.db.fetchval(
            """
            SELECT COUNT(*)
            FROM shortens
            WHERE uploader = $1
            AND shorten_id > time_snowflake(now() - interval '7 days')
            """,
            self.id,
        )

        return {
            "file_byte_limit": limits["blimit"],
            "file_byte_used": bytes_used or 0,
            "shorten_limit": limits["shlimit"],
            "shorten_used": shortens_used,
        }

    async def fetch_stats(self) -> Dict[str, int]:
        """Fetch general statistics about the user."""
        total_files = await _get_uploaded_count_from(self.id, table="files")
        total_shortens = await _get_uploaded_count_from(self.id, table="shortens")
        total_deleted = await _get_uploaded_count_from(
            self.id, table="files", extra_sql="AND deleted = true"
        )

        total_bytes = (
            await app.db.fetchval(
                """
                SELECT SUM(file_size)::bigint
                FROM files
                WHERE uploader = $1
                """,
                self.id,
            )
            or 0
        )

        return {
            "total_files": total_files,
            "total_deleted_files": total_deleted,
            "total_bytes": total_bytes,
            "total_shortens": total_shortens,
        }
