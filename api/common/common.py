# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import logging
import time
from typing import Tuple, Dict, List, Union

from quart import current_app as app

from api.models import User
from api.enums import FileNameType

log = logging.getLogger(__name__)


def _calculate_hash(fhandler) -> str:
    """Generate a hash of the given file.

    This calls the seek(0) of the file handler
    so it can be reused.

    Parameters
    ----------
    fhandler: file object
        Any file-like object.

    Returns
    -------
    str
        The SHA256 hash of the given file.
    """
    hashstart = time.monotonic()
    hash_obj = hashlib.sha256()

    for chunk in iter(lambda: fhandler.read(4096), b""):
        hash_obj.update(chunk)

    # so that we can reuse the same handler
    # later on
    fhandler.seek(0)

    hashend = time.monotonic()
    delta = round(hashend - hashstart, 6)
    log.info(f"Hashing file took {delta} seconds")

    return hash_obj.hexdigest()


async def calculate_hash(fhandle) -> str:
    """Calculate a hash of the given file handle.

    Uses run_in_executor to do the job asynchronously so
    the application doesn't lock up on large files.
    """
    return await app.loop.run_in_executor(None, _calculate_hash, fhandle)


async def get_user_domain_info(
    user_id: int, dtype=FileNameType.FILE
) -> Tuple[int, str, str]:
    """Get information about a user's selected domain.

    Parameters
    ----------
    request: sanic.Request
        Request object for database access.
    user_id: int
        User's snowflake ID.
    dtype, optional: FileNameType
        What type of domain to get? (file or shorten).
        Defaults to file.

    Returns
    -------
    tuple
        with 3 values: domain id, subdomain and the domain string
    """
    user = await User.fetch(user_id)
    assert user is not None

    domain = await app.db.fetchval(
        """
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """,
        user.settings.domain,
    )

    if dtype == FileNameType.SHORTEN and user.settings.shorten_domain is not None:
        shorten_domain = await app.db.fetchval(
            """
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """,
            user.settings.shorten_domain,
        )

        assert shorten_domain is not None

        # if we have all the data on shorten subdomain, return it
        return (
            user.settings.shorten_domain,
            user.settings.shorten_subdomain,
            shorten_domain,
        )

    return user.settings.domain, user.settings.subdomain, domain


def transform_wildcard(domain: str, subdomain_name: str) -> str:
    """Do domain transformations in the case of a wildcard.

    Parameters
    ---------
    domain: str
        The domain as a template for the transformation.
    subdomain_name: str
        The subdomain to be applied on the template.

    Returns
    -------
    str
        The actual domain you should use.
    """
    # Check if it's wildcard and if we have a subdomain set
    if domain[0:2] == "*.":
        if subdomain_name:
            domain = domain.replace("*.", f"{subdomain_name}.")
        else:
            domain = domain.replace("*.", "")

    return domain


async def get_tags() -> List[Dict[str, Union[int, str]]]:
    """Get a mapping from tag ID to tag label."""
    tag_rows = await app.db.fetch(
        "SELECT tag_id, label FROM domain_tags ORDER BY tag_id ASC"
    )
    return [{"id": r["tag_id"], "label": r["label"]} for r in tag_rows]
