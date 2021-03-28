# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any, List, Iterable, Tuple

from quart import current_app as app
from asyncpg import UniqueViolationError, Record

from api.storage import solve_domain
from api.errors import BadInput
from .user import User


class Tag:
    """Represents an elixire domain tag."""

    __slots__ = ("id", "label")

    def __init__(self, id: int, label: str):
        self.id = id
        self.label = label

    @classmethod
    def from_row(cls, row: Record):
        """Create a tag object from an asyncpg record"""
        return cls(row["tag_id"], row["label"])

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label}

    @staticmethod
    async def fetch(tag_id: int) -> Optional["Tag"]:
        label = await app.db.fetchval(
            """
            SELECT label
            FROM domain_tags
            WHERE tag_id = $1
            """,
            tag_id,
        )

        if label is None:
            return None

        return Tag(tag_id, label)

    @staticmethod
    async def fetch_many_by(*, label: str) -> List["Tag"]:
        """Fetch many domain tags via given criteria."""
        rows = await app.db.fetch(
            """
            SELECT tag_id, label
            FROM domain_tags
            WHERE label = $1
            """,
            label,
        )

        return [Tag(row["tag_id"], row["label"]) for row in rows]

    @classmethod
    async def fetch_all_tags(self) -> List["Tag"]:
        rows = await app.db.fetch(
            "SELECT tag_id, label FROM domain_tags ORDER BY tag_id ASC"
        )
        return [Tag(r["tag_id"], r["label"]) for r in rows]

    @staticmethod
    async def create(label: str) -> "Tag":
        """Create a new tag."""
        tag_id: int = await app.db.fetchval(
            """
            INSERT INTO domain_tags
                (label)
            VALUES
                ($1)
            RETURNING tag_id
            """,
            label,
        )

        return Tag(tag_id, label)

    async def delete(self) -> None:
        """Delete the tag."""
        await app.db.execute("DELETE FROM domain_tags WHERE tag_id = $1", self.id)

    async def update(self, **kwargs):
        """Update a domain tag. Receives values to update in the form of
        keyword arguments. The key of the argument MUST be a field in the
        tag table.

        You can not update the tag ID of a tag.

        Updates the model.
        """
        assert "tag_id" not in kwargs

        async with app.db.acquire() as conn:
            async with conn.transaction():
                for field, value in kwargs.items():
                    await conn.execute(
                        f"""
                        UPDATE domain_tags
                        SET {field} = $1
                        WHERE tag_id = $2
                        """,
                        value,
                        self.id,
                    )

                    if field == "label":
                        self.label = value


class Tags(list):
    """Represents a list of :class:`Tag`.
    Implements custom behavior for the `in` operator."""

    def __contains__(self, label) -> bool:
        return next((t for t in self if t.label == label), None) is not None


class Domain:
    """Represents an elixire domain."""

    __slots__ = ("id", "domain", "permissions", "tags", "disabled", "admin_only")

    def __init__(self, row, *, tags: Tags) -> None:
        self.id: int = row["domain_id"]
        self.domain: str = row["domain"]
        self.permissions: int = row["permissions"]
        self.disabled: bool = row["disabled"]
        self.admin_only: bool = row["admin_only"]
        self.tags: Tags = tags

    def __eq__(self, other) -> bool:
        return self.id == other.id

    def __str__(self) -> str:
        return self.domain

    @classmethod
    async def fetch(cls, domain_id: int) -> Optional["Domain"]:
        """Fetch a domain via its ID."""
        row = await app.db.fetchrow(
            """
            SELECT domain_id, domain, permissions, disabled, admin_only
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
    async def fetch_random_id(_cls) -> int:
        return await app.db.fetchval(
            """
            SELECT domain_id
            FROM domains
            ORDER BY RANDOM()
            LIMIT 1
            """
        )

    @staticmethod
    async def fetch_tags(domain_id: int) -> Tags:
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
            "admin_only": self.admin_only,
            "disabled": self.disabled,
            "tags": [{"id": tag.id, "label": tag.label} for tag in self.tags],
        }

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

        consented_clause = "" if not public else "AND user_settings.consented = true"

        row = await app.db.fetchrow(
            f"""
            SELECT
                (SELECT COUNT(*) FROM users
                JOIN user_settings ON user_settings.user_id = users.user_id
                WHERE domain = $1 {consented_clause}) AS user_count,
                (SELECT COUNT(*) FROM shortens
                JOIN users ON users.user_id = shortens.uploader
                JOIN user_settings ON user_settings.user_id = users.user_id
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
            JOIN users ON users.user_id = files.uploader
            JOIN user_settings ON user_settings.user_id = users.user_id
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

    @staticmethod
    async def create(
        name: str,
        *,
        tags: Optional[List[int]] = None,
        permissions: int = 3,
        owner_id: Optional[int] = None,
        disabled: Optional[bool] = False,
        admin_only: Optional[bool] = False,
    ) -> "Domain":
        tags = tags or []

        async with app.db.acquire() as conn:
            async with conn.transaction():

                domain_id = await app.db.fetchval(
                    """
                    INSERT INTO domains
                        (domain, permissions, disabled, admin_only)
                    VALUES
                        ($1, $2, $3, $4)
                    RETURNING domain_id
                    """,
                    name,
                    permissions,
                    disabled,
                    admin_only,
                )

                domain = await Domain.fetch(domain_id)
                assert domain is not None

                if owner_id:
                    await domain.set_owner(owner_id)

                for tag_id in tags:
                    tag = await Tag.fetch(tag_id)
                    assert tag is not None
                    await domain.add_tag(tag)

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
            UPDATE user_settings
            SET domain = 0
            WHERE domain = $1
            """,
            self.id,
        )

        users_shorten_count = await app.db.execute(
            """
            UPDATE user_settings
            SET shorten_domain = 0
            WHERE shorten_domain = $1
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

    async def add_tag(self, tag: Tag) -> None:
        """Add a tag to a domain.

        Updates the model.
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
                tag.id,
            )
        except UniqueViolationError:
            # if tag was already inserted, there isn't
            # any requirement to update the model.
            return

        self.tags.append(tag)

    async def remove_tag(self, tag: Tag) -> None:
        """Remove a tag from a domain.

        Updates the model.
        """

        await app.db.execute(
            """
            DELETE FROM domain_tag_mappings
            WHERE domain_id = $1 AND tag_id = $2
            """,
            self.id,
            tag.id,
        )

        # while it is 99% impossible to have repeated
        # tags in the Tags array (because the database has a
        # PRIMARY KEY set on it), someone messing with the
        # internals might. I'll take my chances and do it the
        # resilient way.

        def _filter_func(item: Tuple[int, Tag]) -> bool:
            _index, upstream_tag = item
            return upstream_tag.id == tag.id

        index_tuples: Iterable[Tuple[int, Tag]] = filter(
            _filter_func, enumerate(self.tags)
        )

        for index, _tag in index_tuples:
            del self.tags[index]

    async def set_domain_tags(self, tags: Tags) -> None:
        """Set tags for a given domain and delete the previously assigned ones.

        Updates the model.
        """
        existing_set = {tag.id for tag in self.tags}
        tags_set = {tag.id for tag in tags}

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
