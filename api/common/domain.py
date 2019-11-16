# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, List, Dict, Union

from quart import current_app as app
from asyncpg import UniqueViolationError

from api.storage import solve_domain
from api.common.utils import dict_
from api.errors import NotFound, BadInput


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


async def _domain_file_stats(domain_id, *, ignore_consented: bool = False) -> tuple:
    """Get domain file stats (count and sum of all bytes)."""

    consented_clause = "" if ignore_consented else "AND users.consented = true"

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
        domain_id,
    )

    return row["count"], int(row["sum"] or 0)


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


async def get_domain_tags(domain_id: int) -> Optional[List[Dict[str, Union[int, str]]]]:
    """Get a domain's tags as a list of objects containing ID and label."""
    return [
        {"id": r["tag_id"], "label": r["label"]}
        for r in await app.db.fetch(
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
    ]


async def is_domain_tags_label(domain_id: int, *, label: str) -> bool:
    """Returns if the given domain has any tags that have the given label"""
    matching_tags = await app.db.fetch(
        """
        SELECT tag_id
        FROM domain_tag_mappings
        JOIN domain_tags
        ON domain_tags.tag_id = domain_tag_mappings.tag_id
        WHERE domain_tags.label = "admin"
          AND domain_id = $1
        """,
        domain_id,
    )

    assert matching_tags is not None
    return bool(matching_tags)


async def is_domain_admin_only(domain_id: int) -> bool:
    return await is_domain_tags_label(domain_id, label="admin_only")


async def get_domain_info(domain_id: int) -> Optional[dict]:
    """Get domain information."""
    raw_info = await app.db.fetchrow(
        """
        SELECT domain, permissions
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    dinfo = dict_(raw_info)
    if dinfo is None:
        return None

    stats = {}

    # doing batch queries should help us speed up the overall request time
    rows = await app.db.fetchrow(
        """
        SELECT
            (SELECT COUNT(*) FROM users WHERE domain = $1),
            (SELECT COUNT(*) FROM shortens WHERE domain = $1)
        """,
        domain_id,
    )

    stats["users"] = rows[0]
    stats["shortens"] = rows[1]

    filestats = await _domain_file_stats(domain_id, ignore_consented=True)
    stats["files"], stats["size"] = filestats

    owner_data = await app.db.fetchrow(
        """
        SELECT user_id::text, username, active, consented, admin, paranoid
        FROM users
        WHERE user_id = (SELECT user_id FROM domain_owners WHERE domain_id = $1)
        """,
        domain_id,
    )

    dict_owner_data = dict_(owner_data)

    return {
        "info": {
            **dinfo,
            **{"owner": dict_owner_data, "tags": await get_domain_tags(domain_id)},
        },
        "stats": stats,
        "public_stats": await get_domain_public(domain_id),
    }


async def get_domain_public(domain_id: int) -> Optional[dict]:
    """Get public information about a domain."""
    public_stats = {}

    rows = await app.db.fetchrow(
        """
        SELECT
            (SELECT COUNT(*) FROM users
            WHERE domain = $1 AND consented = true),
            (SELECT COUNT(*) FROM shortens
            JOIN users ON users.user_id = shortens.uploader
            WHERE shortens.domain = $1 AND users.consented = true)
        """,
        domain_id,
    )

    if rows is None:
        return None

    public_stats["users"] = rows[0]
    public_stats["shortens"] = rows[1]

    filestats = await _domain_file_stats(domain_id)
    public_stats["files"], public_stats["size"] = filestats

    return public_stats


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


async def get_basic_domain(
    domain_id: int, *, raise_notfound: bool = False
) -> Optional[dict]:
    """Fetch a domain by ID."""
    domain_info = await app.db.fetchrow(
        """
        SELECT *
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    if raise_notfound and domain_info is None:
        raise NotFound("This domain does not exist.")

    return domain_info


async def get_basic_domain_by_domain(
    domain: str, *, raise_notfound: bool = False
) -> Optional[dict]:
    """Fetch a domain's info by the string representing it."""

    domains_to_check = solve_domain(domain)
    assert len(domains_to_check) == 3

    domain_info = await app.db.fetchrow(
        """
        SELECT *
        FROM domains
        WHERE domain = $1
        OR domain = $2
        OR domain = $3
        """,
        *domains_to_check,
    )

    if raise_notfound and not domain_info:
        raise NotFound("This domain does not exist in this elixire instance.")

    return domain_info


async def add_domain_tag(domain_id: int, tag_id: int) -> None:
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
    await app.db.execute(
        """
        DELETE FROM domain_tag_mappings
        WHERE domain_id = $1 AND tag_id = $2
        """,
        domain_id,
        tag_id,
    )


async def set_domain_tags(domain_id: int, tags: List[int]) -> None:
    """Forcefully set tags for a given domain."""
    existing_tags = await get_domain_tag_ids(domain_id)
    assert existing_tags is not None

    existing_set = set(existing_tags)
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
    return await app.db.fetchval(
        """
        INSERT INTO domain_tags
            (label)
        VALUES
            ($1)
        RETURNING domain_id
        """,
        label,
    )


async def delete_domain_tag(tag_id: int) -> None:
    await app.db.execute("DELETE FROM domain_tags WHERE tag_id = $1", tag_id)


async def get_all_domains_basic() -> List[dict]:
    return list(
        map(
            dict,
            await app.db.fetch(
                """
                SELECT domain_id, domain
                FROM domains
                ORDER BY domain_id ASC
                """
            ),
        )
    )
