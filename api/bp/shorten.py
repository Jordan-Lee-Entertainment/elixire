# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pathlib
import urllib.parse

from quart import Blueprint, jsonify, current_app as app, request

from api.common.auth import token_check, check_admin
from api.errors import QuotaExploded, BadInput, FeatureDisabled
from api.common import get_user_domain_info, transform_wildcard, FileNameType
from api.common.utils import fetch_domain
from api.snowflake import get_snowflake
from api.permissions import Permissions, domain_permissions
from api.common.profile import gen_user_shortname
from api.storage import object_key

bp = Blueprint("shorten", __name__)


@bp.route("/api/shorten", methods=["POST"])
async def shorten_handler():
    """Handles addition of shortened links."""
    user_id = await token_check()

    try:
        j = await request.get_json()
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
    given_domain, given_subdomain = fetch_domain()

    # Let's actually check if the user is an admin
    # and raise an error if they're not an admin
    if not do_checks:
        await check_admin(user_id, True)

    # Skip checks for admins
    if do_checks:
        if not app.econfig.SHORTENS_ENABLED:
            raise FeatureDisabled("shortens are currently disabled")

        # TODO quota calculations in full sql? is that possible?
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
                f"You already blew your weekly limit of {shorten_limit} shortens"
            )

        if shortens_used and shortens_used + 1 > shorten_limit:
            raise QuotaExploded(
                f"This shorten blows the weekly limit of {shorten_limit} shortens"
            )

    redir_rname, tries = await gen_user_shortname(user_id, "shortens")
    await app.metrics.submit("shortname_gen_tries", tries)

    redir_id = get_snowflake()

    user_domain_id, user_subdomain, user_domain = await get_user_domain_info(
        user_id, FileNameType.SHORTEN
    )
    domain_id = given_domain or user_domain_id
    subdomain = given_subdomain or user_subdomain

    # check if domain is uploadable
    await domain_permissions(app, domain_id, Permissions.SHORTEN)

    # resolve the given (domain_id, subdomain_name) into a string
    if given_domain is None:
        domain = user_domain
    else:
        domain = await app.db.fetchval(
            """
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """,
            given_domain,
        )
    domain = transform_wildcard(domain, subdomain)

    await app.db.execute(
        """
        INSERT INTO shortens (shorten_id, filename,
            uploader, redirto, domain, subdomain)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        redir_id,
        redir_rname,
        user_id,
        url_toredir,
        domain_id,
        subdomain,
    )

    await app.storage.set_with_ttl(
        object_key("redir", domain_id, subdomain, redir_rname), url_toredir, 600
    )

    # appended to generated filename
    dpath = pathlib.Path(domain)
    fpath = dpath / "s" / redir_rname

    return jsonify({"url": f"https://{str(fpath)}"})
