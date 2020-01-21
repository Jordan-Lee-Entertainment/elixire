# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - index routes
    Those routes can be used by anyone, they differ from misc
    because those provide public functionality (where as /api/hello
    isn't used by a client).
"""
from quart import Blueprint, jsonify, current_app as app
from api.models import Domain

bp = Blueprint("index", __name__)


@bp.route("/domains")
async def domainlist_handler():
    """Gets the domain list."""

    domain_ids = await app.db.fetch(
        """
        SELECT domain_id
        FROM domains
        """
    )

    return jsonify(
        {
            "domains": [
                (await Domain.fetch(row["domain_id"])).to_dict() for row in domain_ids
            ]
        }
    )
