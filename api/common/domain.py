# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Union
from quart import current_app as app
from api.models import Domain


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
