# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - index routes
    Those routes can be used by anyone, they differ from misc
    because those provide public functionality (where as /api/hello
    isn't used by a client).
"""
from quart import Blueprint, jsonify, current_app as app

from api.common.domain import get_domain_tag_ids
from api.common.common import get_tags

bp = Blueprint("index", __name__)


@bp.route("/domains")
async def domainlist_handler():
    """Gets the domain list."""

    domains = await app.db.fetch(
        """
        SELECT domain_id, domain
        FROM domains
        ORDER BY domain_id ASC
        """
    )

    domain_tags = {}

    for drow in domains:
        domain_id = drow["domain_id"]
        tag_ids = await get_domain_tag_ids(domain_id)
        domain_tags[domain_id] = tag_ids

    return jsonify(
        {"domains": dict(domains), "domain_tags": domain_tags, "tags": await get_tags()}
    )
