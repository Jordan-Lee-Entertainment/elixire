# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import urllib.parse

from quart import Blueprint, jsonify, redirect, current_app as app, request

from ..common.utils import service_url
from ..common.auth import gen_shortname, token_check, check_admin
from ..errors import NotFound, QuotaExploded, BadInput, FeatureDisabled
from ..common import get_domain_info, transform_wildcard, FileNameType
from ..snowflake import get_snowflake
from ..permissions import Permissions, domain_permissions

bp = Blueprint("shorten", __name__)


# TODO move this into fetch bp
@bp.get("/s/<filename>")
async def shorten_serve_handler(filename):
    """Handles serving of shortened links."""
    storage = app.storage
    domain_id = await storage.get_domain_id(request.headers["host"])
    url_toredir = await storage.get_urlredir(filename, domain_id)

    if not url_toredir:
        raise NotFound("No shortened links found with this name " "on this domain.")

    return redirect(url_toredir)


@bp.post("/api/shorten")
async def shorten_handler():
    """Handles addition of shortened links."""
    user_id = await token_check()

    j = await request.get_json()

    try:
        url_toredir = str(j["url"])
        url_parsed = urllib.parse.urlparse(url_toredir)
    except (TypeError, ValueError):
        raise BadInput("Invalid URL")

    if url_parsed.scheme not in ("https", "http"):
        raise BadInput(
            f"Invalid URI scheme({url_parsed.scheme}). "
            "Only https and http are allowed."
        )

    if len(url_toredir) > app.econfig.MAX_SHORTEN_URL_LEN:
        raise BadInput(
            f"Your URL is way too long ({len(url_toredir)} "
            f"> {app.econfig.MAX_SHORTEN_URL_LEN})."
        )

    # Check if admin is set in get values, if not, do checks
    # If it is set, and the admin value is truthy, do not do checks
    do_checks = not ("admin" in request.args and request.args["admin"])

    # Let's actually check if the user is an admin
    # and raise an error if they're not an admin
    if not do_checks:
        await check_admin(user_id, True)

    # Skip checks for admins
    if do_checks:
        if not app.econfig.SHORTENS_ENABLED:
            raise FeatureDisabled("shortens are currently disabled")

        shortens_used = await app.db.fetch(
            """
        SELECT shorten_id
        FROM shortens
        WHERE uploader = $1
        AND shorten_id > time_snowflake(now() - interval '7 days')
        """,
            user_id,
        )

        shortens_used = len(shortens_used)

        shorten_limit = await app.db.fetchval(
            """
        SELECT shlimit
        FROM limits
        WHERE user_id = $1
        """,
            user_id,
        )

        if shortens_used and shortens_used > shorten_limit:
            raise QuotaExploded(
                "You already blew your weekly" f" limit of {shorten_limit} shortens"
            )

        if shortens_used and shortens_used + 1 > shorten_limit:
            raise QuotaExploded(
                "This shorten blows the weekly limit of" f" {shorten_limit} shortens"
            )

    redir_rname, tries = await gen_shortname(user_id, "shortens")
    await app.metrics.submit("shortname_gen_tries", tries)

    redir_id = get_snowflake()
    domain_id, subdomain_name, domain = await get_domain_info(
        user_id, FileNameType.SHORTEN
    )

    await domain_permissions(domain_id, Permissions.SHORTEN)
    domain = transform_wildcard(domain, subdomain_name)

    # make sure cache doesn't fuck up
    await app.storage.raw_invalidate(f"redir:{domain_id}:{redir_rname}")

    await app.db.execute(
        """
    INSERT INTO shortens (shorten_id, filename,
        uploader, redirto, domain)
    VALUES ($1, $2, $3, $4, $5)
    """,
        redir_id,
        redir_rname,
        user_id,
        url_toredir,
        domain_id,
    )

    return jsonify(
        {"url": service_url(domain, f"/s/{redir_rname}"), "shortname": redir_rname}
    )
