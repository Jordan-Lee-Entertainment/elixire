# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, current_app as app, jsonify

from api.common.auth import token_check
from api.common.domain import get_domain_public, get_domain_tags


bp = Blueprint("personal_stats", __name__)
log = logging.getLogger(__name__)


@bp.route("/my_domains")
async def personal_domain_stats():
    """Fetch information about the domains you own."""
    user_id = await token_check()
    db = app.db

    domain_ids = await db.fetch(
        """
        SELECT domain_id
        FROM domain_owners
        WHERE user_id = $1
        """,
        user_id,
    )

    res = {}

    for row in domain_ids:
        domain_id = row["domain_id"]

        domain_info = await db.fetchrow(
            """
            SELECT domain, permissions
            FROM domains
            WHERE domain_id = $1
            """,
            domain_id,
        )

        dinfo = dict(domain_info)

        public = await get_domain_public(domain_id)
        res[domain_id] = {
            "info": {**dinfo, **{"tags": await get_domain_tags(domain_id)}},
            "stats": public,
        }

    return jsonify(res)
