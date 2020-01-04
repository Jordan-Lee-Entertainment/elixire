# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Union
from quart import current_app as app


class Domain:
    """Represents an elixire domain."""

    __slots__ = ("id", "admin_only", "official", "domain", "permissions")

    def __init__(self, row) -> None:
        self.id: int = row["domain_id"]
        self.admin_only: bool = row["admin_only"]
        self.official: bool = row["official"]
        self.domain: str = row["domain"]
        self.permissions: int = row["permissions"]

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __str__(self) -> str:
        return self.domain

    @classmethod
    async def fetch(cls, domain_id: int) -> Optional["Domain"]:
        """Fetch a domain via its ID."""
        row = await app.db.fetchrow(
            f"""
            SELECT
                domain_id, admin_only, official, domain, permissions
            FROM domains
            WHERE domain_id = $1
            LIMIT 1
            """,
            domain_id,
        )

        return Domain(row) if row is not None else None

    def to_dict(self) -> Dict[str, Union[int, bool, str]]:
        """Return the domain as a dictionary."""
        return {
            "id": self.id,
            "admin_only": self.admin_only,
            "official": self.official,
            "domain": self.domain,
            "permissions": self.permissions,
        }
