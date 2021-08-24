# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


async def _domain_file_stats(db, domain_id, *, ignore_consented: bool = False) -> tuple:
    """Get domain file stats (count and sum of all bytes)."""

    consented_clause = "" if ignore_consented else "AND users.consented = true"

    row = await db.fetchrow(
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


async def get_domain_info(db, domain_id) -> dict:
    """Get domain information."""
    raw_info = await db.fetchrow(
        """
    SELECT domain, official, admin_only, permissions
    FROM domains
    WHERE domain_id = $1
    """,
        domain_id,
    )

    dinfo = dict(raw_info)
    dinfo["cf_enabled"] = False

    stats = {}

    stats["users"] = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM users
    WHERE domain = $1
    """,
        domain_id,
    )

    stats["files"] = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM files
    WHERE domain = $1
    """,
        domain_id,
    )

    filestats = await _domain_file_stats(db, domain_id, ignore_consented=True)
    stats["files"], stats["size"] = filestats

    stats["shortens"] = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    WHERE domain = $1
    """,
        domain_id,
    )

    owner_id = await db.fetchval(
        """
    SELECT user_id
    FROM domain_owners
    WHERE domain_id = $1
    """,
        domain_id,
    )

    owner_data = await db.fetchrow(
        """
    SELECT username, active, consented, admin, paranoid
    FROM users
    WHERE user_id = $1
    """,
        owner_id,
    )

    if owner_data:
        downer = {**dict(owner_data), **{"user_id": str(owner_id)}}
    else:
        downer = None

    return {
        "info": {**dinfo, **{"owner": downer}},
        "stats": stats,
        "public_stats": await get_domain_public(db, domain_id),
    }


async def get_domain_public(db, domain_id) -> dict:
    """Get public information about a domain."""
    public_stats = {}

    public_stats["users"] = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM users
    WHERE domain = $1 AND consented = true
    """,
        domain_id,
    )

    filestats = await _domain_file_stats(db, domain_id)
    public_stats["files"], public_stats["size"] = filestats

    public_stats["shortens"] = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    JOIN users
      ON users.user_id = shortens.uploader
    WHERE shortens.domain = $1 AND users.consented = true
    """,
        domain_id,
    )

    return public_stats
