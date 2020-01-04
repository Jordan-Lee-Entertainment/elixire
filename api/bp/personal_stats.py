# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, current_app as app, jsonify

from api.common.auth import token_check
from api.models import Domain


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

    res = []

    for row in domain_ids:
        domain = await Domain.fetch(row["domain_id"])
        assert domain is not None

        domain_dict = domain.to_dict()
        # TODO
        # domain_dict["stats"] = await domain.fetch_stats(public=True)
        res.append(domain_dict)

    return jsonify({"domains": res})
