# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import string
import logging
import secrets
from typing import Tuple
from quart import current_app as app

log = logging.getLogger(__name__)
ALPHABET = string.ascii_lowercase + string.digits

__all__ = ["generate_shortname"]


def raw_generate_shortname(length: int) -> str:
    """Generate a random shortname."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


async def generate_shortname(
    length: int = 3, table: str = "files", _curc: int = 0
) -> Tuple[str, int]:
    """Generate a unique random shortname.

    To guarantee that the generated shortnames will
    be unique, we query our DB if the generated
    shortname already exists, and retry if it does.

    Parameters
    ----------
    length, optional: int
        Minimal amount of characters to use, default 3.
        Grows with the amount of failed generations.

    table, optional: str
        The table to generate a unique shortname for,
        by default being the 'files' table.

    Returns
    -------
    tuple
        Containing the generated shortname
        and how many tries happened to generate it.

    Raises
    ------
    RuntimeError
        If it tried to generate a shortname with more than 10 letters.
    """
    if length > 10:
        raise RuntimeError("Failed to generate a shortname")

    try_count = 0

    field = "file_id" if table == "files" else "shorten_id"

    for try_count in range(10):
        possible_shortname = raw_generate_shortname(length)

        filerow = await app.db.fetchrow(
            f"""
            SELECT {field}
            FROM {table}
            WHERE filename = $1
            """,
            possible_shortname,
        )

        if not filerow:
            total = _curc + try_count
            log.info(f"Took {total} retries to " f"generate {possible_shortname!r}")
            return possible_shortname, total

    # if 10 tries didnt work, try generating with length+1
    return await generate_shortname(length + 1, table, _curc + try_count + 1)
