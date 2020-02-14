# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any, List
from collections import namedtuple
from quart import current_app as app
from asyncpg import UniqueViolationError
from .user import User
from api.storage import solve_domain
from api.errors import BadInput


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

        return (
            cls(row, tags=await cls.fetch_tags(domain_id)) if row is not None else None
        )

    @classmethod
    async def fetch_tags(self, domain_id: int) -> Tags:
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

        return Tags([Tag.from_row(r) for r in tag_rows])

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

    async def fetch_owner(self) -> Optional[User]:
        """Fetch the owner of a domain."""
        owner_id = await app.db.fetchval(
            "SELECT user_id FROM domain_owners WHERE domain_id = $1", self.id
        )

        if owner_id is None:
            return None

        return await User.fetch(owner_id)

    @classmethod
    async def create(
        _,
        name: str,
        *,
        tags: Optional[List[int]] = None,
        permissions: int = 3,
        owner_id: Optional[int] = None,
    ) -> "Domain":
        tags = tags or []

        async with app.db.acquire() as conn:
            async with conn.transaction():

                domain_id = await app.db.fetchval(
                    """
                    INSERT INTO domains
                        (domain, permissions)
                    VALUES
                        ($1, $2)
                    RETURNING domain_id
                    """,
                    name,
                    permissions,
                )

                domain = Domain(
                    {
                        "domain_id": domain_id,
                        "domain": name,
                        "permissions": permissions,
                    },
                    tags=Tags([]),
                )

                if owner_id:
                    await domain.set_owner(owner_id)

                for tag_id in tags:
                    await domain.add_tag(tag_id)

        # invalidate cache
        possibilities = solve_domain(domain.domain)
        await app.storage.raw_invalidate(*possibilities)

        return domain

    async def delete(self) -> dict:
        """Delete a domain.

        The related cache keys will be invalidated for you.
        """
        if self.id == 0:
            raise BadInput("The root domain can not be deleted")

        domain_name = await app.db.fetchval(
            """
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """,
            self.id,
        )

        files_count = await app.db.execute(
            """
            UPDATE files set domain = 0 WHERE domain = $1
            """,
            self.id,
        )

        shorten_count = await app.db.execute(
            """
            UPDATE shortens set domain = 0 WHERE domain = $1
            """,
            self.id,
        )

        users_count = await app.db.execute(
            """
            UPDATE users set domain = 0 WHERE domain = $1
            """,
            self.id,
        )

        users_shorten_count = await app.db.execute(
            """
            UPDATE users set shorten_domain = 0 WHERE shorten_domain = $1
            """,
            self.id,
        )

        await app.db.execute(
            """
            DELETE FROM domain_owners
            WHERE domain_id = $1
            """,
            self.id,
        )

        result = await app.db.execute(
            """
            DELETE FROM domains
            WHERE domain_id = $1
            """,
            self.id,
        )

        # invalidate cache
        keys = solve_domain(domain_name)
        await app.storage.raw_invalidate(*keys)

        # TODO make this a namedtuple
        return {
            "file_move_result": files_count,
            "shorten_move_result": shorten_count,
            "users_move_result": users_count,
            "users_shorten_move_result": users_shorten_count,
            "result": result,
        }

    async def set_owner(self, owner_id: int) -> None:
        """Set domain owner for the given domain."""
        await app.db.execute(
            """
            INSERT INTO domain_owners (domain_id, user_id)
            VALUES ($1, $2)
            ON CONFLICT ON CONSTRAINT domain_owners_pkey
            DO UPDATE
                SET user_id = $2
                WHERE domain_owners.domain_id = $1
            """,
            self.id,
            owner_id,
        )

    async def add_tag(self, tag_id: int) -> None:
        """Add a tag to a domain.

        Keep in mind to refetch your model on update.
        """
        try:
            await app.db.execute(
                """
                INSERT INTO domain_tag_mappings
                    (domain_id, tag_id)
                VALUES
                    ($1, $2)
                """,
                self.id,
                tag_id,
            )
        except UniqueViolationError:
            pass

    async def remove_domain_tag(self, tag_id: int) -> None:
        """Remove a tag from a domain.

        Keep in mind to refetch your model on update.
        """

        await app.db.execute(
            """
            DELETE FROM domain_tag_mappings
            WHERE domain_id = $1 AND tag_id = $2
            """,
            self.id,
            tag_id,
        )

    async def set_domain_tags(self, tags: Tags) -> None:
        """Set tags for a given domain and delete the previously assigned ones.

        Updates the model.
        """
        existing_set = {tag.id for tag in self.tags}
        tags_set = set(tags)

        to_add = tags_set - existing_set
        to_remove = existing_set - tags_set

        async with app.db.acquire() as conn:
            async with conn.transaction():
                await app.db.executemany(
                    """
                    INSERT INTO domain_tag_mappings (domain_id, tag_id)
                    VALUES ($1, $2)
                    """,
                    [(self.id, tag_id) for tag_id in to_add],
                )

                await app.db.executemany(
                    """
                    DELETE FROM domain_tag_mappings
                    WHERE domain_id = $1 AND tag_id = $2
                    """,
                    [(self.id, tag_id) for tag_id in to_remove],
                )

        self.tags = tags

    async def fetch_info_dict(self) -> dict:
        # TODO make this a namedtuple?
        domain_dict = self.to_dict()
        domain_dict["stats"] = await self.fetch_stats()
        domain_dict["public_stats"] = await self.fetch_stats(public=True)

        owner = await self.fetch_owner()
        domain_dict["owner"] = owner.to_dict() if owner else None
        return domain_dict
