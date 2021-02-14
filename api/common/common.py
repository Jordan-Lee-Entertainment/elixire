# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Dict, List, Union

from quart import current_app as app


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
