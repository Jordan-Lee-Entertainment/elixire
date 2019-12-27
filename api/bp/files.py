# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import logging

from quart import Blueprint, jsonify, request, current_app as app

from api.common.auth import token_check
from api.errors import BadInput

bp = Blueprint("files", __name__)
log = logging.getLogger(__name__)


async def domain_list():
    """Returns a dictionary with domain IDs mapped to domain names"""
    return dict(
        await app.db.fetch(
            """
            SELECT domain_id, domain
            FROM domains
            """
        )
    )


def construct_domain(domains: dict, obj: dict) -> str:
    """Construct a full domain, given the list of domains and the object to
    put subdomains on. the default is "wildcard"."""
    domain = domains[obj["domain"]]
    subdomain = obj["subdomain"]

    if domain.startswith("*."):
        domain = domain.replace("*", subdomain or "wildcard")

    return domain


# TODO: see https://gitlab.com/elixire/elixire/issues/121
@bp.route("/list")
async def list_handler():
    """Get list of files."""
    # TODO: simplify this code
    try:
        page = int(request.args["page"])
    except (ValueError, KeyError):
        raise BadInput("Page parameter needs to be supplied correctly.")

    user_id = await token_check()
    domains = await domain_list()

    user_files = await app.db.fetch(
        """
        SELECT file_id, filename, file_size, fspath, mimetype, domain, subdomain
        FROM files
        WHERE uploader = $1
        AND deleted = false
        ORDER BY file_id DESC

        LIMIT 100
        OFFSET ($2 * 100)
        """,
        user_id,
        page,
    )

    user_shortens = await app.db.fetch(
        """
        SELECT shorten_id, filename, redirto, domain, subdomain
        FROM shortens
        WHERE uploader = $1
        AND deleted = false
        ORDER BY shorten_id DESC

        LIMIT 100
        OFFSET ($2 * 100)
        """,
        user_id,
        page,
    )

    use_https = app.econfig.USE_HTTPS
    prefix = "https://" if use_https else "http://"

    filenames = {}
    for ufile in user_files:
        filename = ufile["filename"]
        mime = ufile["mimetype"]
        domain = construct_domain(domains, ufile)

        basename = os.path.basename(ufile["fspath"])
        ext = basename.split(".")[-1]

        fullname = f"{filename}.{ext}"
        file_url = f"{prefix}{domain}/i/{fullname}"

        # default thumb size is small
        file_url_thumb = (
            f"{prefix}{domain}/t/s{fullname}" if mime.startswith("image/") else file_url
        )

        filenames[filename] = {
            "snowflake": str(ufile["file_id"]),
            "shortname": filename,
            "size": ufile["file_size"],
            "mimetype": mime,
            "url": file_url,
            "thumbnail": file_url_thumb,
        }

    shortens = {}
    for ushorten in user_shortens:
        filename = ushorten["filename"]
        domain = construct_domain(domains, ushorten)

        shorten_url = f"{prefix}{domain}/s/{filename}"

        shortens[filename] = {
            "snowflake": str(ushorten["shorten_id"]),
            "shortname": filename,
            "redirto": ushorten["redirto"],
            "url": shorten_url,
        }

    return jsonify({"success": True, "files": filenames, "shortens": shortens})
