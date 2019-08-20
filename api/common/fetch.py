# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


from typing import Optional, Dict, Tuple, Coroutine, Any, Callable

from quart import current_app as app


async def get_file_id(file_name: str) -> Optional[int]:
    """Get a file ID, given a file shortname."""
    return await app.db.fetchval(
        """
        SELECT file_id
        FROM files
        WHERE filename = $1
        """,
        file_name,
    )


async def get_shorten_id(shorten_name: str) -> Optional[int]:
    """Get a shorten ID, given a shorten shortname."""
    return await app.db.fetchval(
        """
        SELECT shorten_id
        FROM shortens
        WHERE filename = $1
        """,
        shorten_name,
    )


async def get_file(file_id: int) -> Optional[dict]:
    """Get a dictionary holding file information."""
    row = await app.db.fetchrow(
        """
        SELECT file_id, mimetype, filename, file_size,
            uploader, fspath, deleted, domain, subdomain
        FROM files
        WHERE file_id = $1
        """,
        file_id,
    )

    if row is None:
        return None

    drow = dict(row)
    drow["file_id"] = str(drow["file_id"])
    drow["uploader"] = str(drow["uploader"])

    return drow


async def get_shorten(shorten_id: int) -> Optional[dict]:
    """Get a dictionary holding shorten information."""

    # NOTE: this is really a copypaste from get_file.
    # the old function was unified, called generic_namefetch,
    # it was shitty... so i split it into two.

    row = await app.db.fetchrow(
        """
        SELECT shorten_id, filename, redirto, uploader,
            deleted, domain, subdomain
        FROM shortens
        WHERE shorten_id = $1
        """,
        shorten_id,
    )

    if row is None:
        return None

    drow = dict(row)
    drow["shorten_id"] = str(drow["shorten_id"])
    drow["uploader"] = str(drow["uploader"])

    return drow


OBJ_MAPPING: Dict[
    str,
    Tuple[
        Callable[[str], Coroutine[Any, Any, Optional[int]]],
        Callable[[int], Coroutine[Any, Any, Optional[dict]]],
    ],
] = {"file": (get_file_id, get_file), "shorten": (get_shorten_id, get_shorten)}
