# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pathlib
import urllib.parse

from quart import Blueprint, jsonify, current_app as app, request
from winter import get_snowflake

from api.common.auth import token_check, check_admin
from api.errors import QuotaExploded, BadInput, FeatureDisabled
from api.enums import FileNameType
from api.common.utils import resolve_domain
from api.common.profile import gen_user_shortname
from api.storage import object_key
from api.scheduled_deletes import maybe_schedule_deletion, validate_request_duration

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

    validate_request_duration()

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

    redir_rname, tries = await gen_user_shortname(user_id, table="shortens")
    await app.metrics.submit("shortname_gen_tries", tries)

    redir_id = get_snowflake()

    domain_id, domain, subdomain_name = await resolve_domain(
        user_id, FileNameType.SHORTEN
    )

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
        subdomain_name,
    )

    # appended to generated filename
    dpath = pathlib.Path(domain)
    fpath = dpath / "s" / redir_rname

    res = {"url": f"https://{str(fpath)}"}
    deletion_job_id = await maybe_schedule_deletion(user_id, shorten_id=redir_id)
    if deletion_job_id:
        res["scheduled_delete_job_id"] = deletion_job_id

    await app.storage.set_with_ttl(
        object_key("redir", domain_id, subdomain_name, redir_rname), url_toredir, 600
    )

    return jsonify(res)
