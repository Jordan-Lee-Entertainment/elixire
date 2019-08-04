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

from api.errors import FailedAuth
from api.common.auth import token_check, check_admin

bp = Blueprint("index", __name__)


@bp.route("/domains")
async def domainlist_handler():
    """Gets the domain list.

    Returns admin-only domains if an
    Authorization header is given.
    """

    # Only check if user's token is valid and their admin status
    # if they gave authorization.
    try:
        user_id = await token_check()
        is_admin = await check_admin(user_id, False)
    except FailedAuth:
        is_admin = False

    adm_string = "" if is_admin else "WHERE admin_only = false"
    domains = await app.db.fetch(
        f"""
        SELECT domain_id, domain
        FROM domains
        {adm_string}
        ORDER BY official DESC, domain_id ASC
        """
    )

    adm_string_official = "" if is_admin else "AND admin_only = false"
    official_domains = await app.db.fetch(
        f"""
        SELECT domain_id
        FROM domains
        WHERE official = true {adm_string_official}
        ORDER BY domain_id ASC
        """
    )

    # dear god
    official_domains = [row["domain_id"] for row in official_domains]

    return jsonify({"domains": dict(domains), "officialdomains": official_domains})
