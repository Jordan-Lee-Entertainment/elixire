# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any
from quart import current_app as app
from collections import namedtuple


class Tag(namedtuple("Tag", ["id", "label"])):
    @classmethod
    def from_row(cls, row):
        """Create a tag object from a row"""
        return cls(row["tag_id"], row["label"])


class Tags(list):
    """Represents a list of :class:`Tag`.
    Implements custom behavior for the `in` operator."""

    def __contains__(self, label) -> bool:
        return next((t for t in self if t.label == label), None) is not None


class Domain:
    """Represents an elixire domain."""

    __slots__ = ("id", "domain", "permissions", "tags")

    def __init__(self, row, *, tags: Tags) -> None:
        self.id: int = row["domain_id"]
        self.domain: str = row["domain"]
        self.permissions: int = row["permissions"]
        self.tags: Tags = tags

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __str__(self) -> str:
        return self.domain

    @classmethod
    async def fetch(cls, domain_id: int) -> Optional["Domain"]:
        """Fetch a domain via its ID."""
        row = await app.db.fetchrow(
            f"""
            SELECT domain_id, domain, permissions
            FROM domains
            WHERE domain_id = $1
            LIMIT 1
            """,
            domain_id,
        )

        tag_rows = await app.db.fetch(
            """
            SELECT domain_tags.tag_id, domain_tags.label
            FROM domain_tag_mappings
            JOIN domain_tags
            ON domain_tags.tag_id = domain_tag_mappings.tag_id
            WHERE domain_id = $1
            ORDER BY domain_tags.tag_id ASC
            """,
            domain_id,
        )

        return (
            Domain(row, tags=Tags([Tag.from_row(r) for r in tag_rows]))
            if row is not None
            else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return the domain as a dictionary."""
        return {
            "id": self.id,
            "domain": self.domain,
            "permissions": self.permissions,
            "tags": [{"id": tag.id, "label": tag.label} for tag in self.tags],
        }

    @property
    def admin_only(self) -> bool:
        """Returns if a domain can only be used by Admins."""
        return "admin_only" in self.tags

    @property
    def official(self) -> bool:
        """Returns if a domain is official.

        Official domains, as defined in elixi.re (but not required to be defined
        as that in other instances), are domains that the instance owners
        have full control over the DNS records of.
        """
        return "official" in self.tags

    async def fetch_stats(self, *, public: bool = False) -> dict:
        """Fetch statistics about a domain. Returns a dictionary containing
         - the total count of users using the domain
         - the total count of shortens
         - the total count of files
         - the total size of the files in the domain
        """
        stats = {}

        consented_clause = "" if not public else "AND users.consented = true"

        row = await app.db.fetchrow(
            f"""
            SELECT
                (SELECT COUNT(*) FROM users
                WHERE domain = $1 {consented_clause}) AS user_count,
                (SELECT COUNT(*) FROM shortens
                JOIN users ON users.user_id = shortens.uploader
                WHERE shortens.domain = $1 {consented_clause}) AS shorten_count
            """,
            self.id,
        )

        assert row is not None

        stats["user_count"] = row["user_count"]
        stats["shorten_count"] = row["shorten_count"]

        row = await app.db.fetchrow(
            f"""
            SELECT COUNT(*), SUM(file_size)
            FROM files
            JOIN users
            ON users.user_id = files.uploader
            WHERE files.domain = $1
            AND files.deleted = false
            {consented_clause}
            """,
            self.id,
        )

        stats["files"] = {
            "count": row["count"],
            "total_file_bytes": int(row["sum"] or 0),
        }

        return stats
