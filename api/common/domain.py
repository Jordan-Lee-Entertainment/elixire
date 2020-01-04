# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, List, Dict, Union

from quart import current_app as app
from asyncpg import UniqueViolationError

from api.storage import solve_domain
from api.errors import NotFound, BadInput
from api.models import User, Domain


async def create_domain(
    domain: str,
    *,
    tags: Optional[List[int]] = None,
    permissions: int = 3,
    owner_id: int = None,
) -> int:
    """Create a domain.

    The related cache keys will be invalidated for you.
    """
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
                domain,
                permissions,
            )

            if owner_id:
                await set_domain_owner(domain_id, owner_id)

            for tag_id in tags:
                await add_domain_tag(domain_id, tag_id)

    # invalidate cache
    possibilities = solve_domain(domain)
    await app.storage.raw_invalidate(*possibilities)

    return domain_id


async def delete_domain(domain_id: int) -> dict:
    """Delete a domain.

    The related cache keys will be invalidated for you.
    """
    if domain_id == 0:
        raise BadInput("The root domain can not be deleted")

    domain_name = await app.db.fetchval(
        """
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    files_count = await app.db.execute(
        """
        UPDATE files set domain = 0 WHERE domain = $1
        """,
        domain_id,
    )

    shorten_count = await app.db.execute(
        """
        UPDATE shortens set domain = 0 WHERE domain = $1
        """,
        domain_id,
    )

    users_count = await app.db.execute(
        """
        UPDATE users set domain = 0 WHERE domain = $1
        """,
        domain_id,
    )

    users_shorten_count = await app.db.execute(
        """
        UPDATE users set shorten_domain = 0 WHERE shorten_domain = $1
        """,
        domain_id,
    )

    await app.db.execute(
        """
        DELETE FROM domain_owners
        WHERE domain_id = $1
        """,
        domain_id,
    )

    result = await app.db.execute(
        """
        DELETE FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    # invalidate cache
    keys = solve_domain(domain_name)
    await app.storage.raw_invalidate(*keys)

    return {
        "file_move_result": files_count,
        "shorten_move_result": shorten_count,
        "users_move_result": users_count,
        "users_shorten_move_result": users_shorten_count,
        "result": result,
    }


async def get_domain_tag_ids(domain_id: int) -> Optional[List[int]]:
    """Get a domain's tag IDs."""
    return [
        r["tag_id"]
        for r in await app.db.fetch(
            """
            SELECT tag_id
            FROM domain_tag_mappings
            WHERE domain_id = $1
            ORDER BY tag_id ASC
            """,
            domain_id,
        )
    ]


async def get_domain_info(domain_id: int) -> Optional[dict]:
    """Get domain information."""
    domain = await Domain.fetch(domain_id)
    if domain is None:
        return None

    domain_dict = domain.to_dict()
    domain_dict["stats"] = await domain.fetch_stats()
    domain_dict["public_stats"] = await domain.fetch_stats(public=True)

    owner = await domain.fetch_owner()
    domain_dict["owner"] = owner.to_dict() if owner else None
    return domain_dict


async def set_domain_owner(domain_id: int, owner_id: int) -> None:
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
        domain_id,
        owner_id,
    )


async def add_domain_tag(domain_id: int, tag_id: int) -> None:
    """Add a tag to a domain."""
    try:
        await app.db.execute(
            """
            INSERT INTO domain_tag_mappings
                (domain_id, tag_id)
            VALUES
                ($1, $2)
            """,
            domain_id,
            tag_id,
        )
    except UniqueViolationError:
        pass


async def remove_domain_tag(domain_id: int, tag_id: int) -> None:
    """Remove a tag from a domain."""
    await app.db.execute(
        """
        DELETE FROM domain_tag_mappings
        WHERE domain_id = $1 AND tag_id = $2
        """,
        domain_id,
        tag_id,
    )


async def set_domain_tags(domain_id: int, tags: List[int]) -> None:
    """Set tags for a given domain and delete the previously assigned ones."""
    domain = await Domain.fetch(domain_id)
    assert domain is not None

    existing_set = {tag.id for tag in domain.tags}
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
                [(domain_id, tag_id) for tag_id in to_add],
            )

            await app.db.executemany(
                """
                DELETE FROM domain_tag_mappings
                WHERE domain_id = $1 AND tag_id = $2
                """,
                [(domain_id, tag_id) for tag_id in to_remove],
            )


async def create_domain_tag(label: str) -> int:
    """Create a domain tag and return its ID."""
    return await app.db.fetchval(
        """
        INSERT INTO domain_tags
            (label)
        VALUES
            ($1)
        RETURNING tag_id
        """,
        label,
    )


async def delete_domain_tag(tag_id: int) -> None:
    """Delete a domain tag by ID."""
    await app.db.execute("DELETE FROM domain_tags WHERE tag_id = $1", tag_id)


async def update_domain_tag(tag_id: int, **kwargs) -> Dict[str, Union[int, str]]:
    """Update a domain tag. Receives values to update in the form of
    keyword arguments. The key of the argument MUST be a field in the
    tag table.

    Returns a dictionary containing the updated tag object.
    """
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
                    tag_id,
                )

    row = await app.db.fetchrow(
        """
        SELECT tag_id AS id, label
        FROM domain_tags
        WHERE tag_id = $1
        """,
        tag_id,
    )

    assert row is not None
    return dict(row)
