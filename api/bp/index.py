# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - index routes
    Those routes can be used by anyone, they differ from misc
    because those provide public functionality (where as /api/hello
    isn't used by a client).
"""
from quart import Blueprint, jsonify

from api.common.domain import get_domain_tags, get_all_domains_basic

bp = Blueprint("index", __name__)


@bp.route("/domains")
async def domainlist_handler():
    """Gets the domain list."""
    domain_data = await get_all_domains_basic()

    result = [
        {
            "id": drow["domain_id"],
            "domain": drow["domain"],
            "tags": await get_domain_tags(drow["domain_id"]),
        }
        for drow in domain_data
    ]

    return jsonify({"domains": result})
