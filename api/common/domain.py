# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional

# TODO replace by app and remove current app parameters
from quart import current_app as app

from api.common.utils import dict_
from api.errors import NotFound


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


async def get_domain_info(domain_id: int) -> Optional[dict]:
    """Get domain information."""
    raw_info = await app.db.fetchrow(
        """
        SELECT domain, official, admin_only, permissions
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    dinfo = dict_(raw_info)
    if dinfo is None:
        return None

    dinfo["cf_enabled"] = False

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
        "info": {**dinfo, **{"owner": dict_owner_data}},
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

    # there can be three types of inputs
    #  - just the domain (a.tld)
    #  - the domain with a subdomain (b.a.tld)
    #  - the wildcard domain (*.a.tld)
    # all three can exist inside the domains table.
    # since we don't know which domain we're given, we transform
    # it into all three, then give a search.

    subd_wildcard_name = domain.replace(domain.split(".")[0], "*")
    domain_wildcard_name = "*." + domain

    domain_info = await app.db.fetchrow(
        """
        SELECT *
        FROM domains
        WHERE domain = $1
        OR domain = $2
        OR domain = $3
        """,
        domain,
        subd_wildcard_name,
        domain_wildcard_name,
    )

    if raise_notfound and not domain_info:
        raise NotFound("This domain does not exist in this elixire instance.")

    return domain_info
