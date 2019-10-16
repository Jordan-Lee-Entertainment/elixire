# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import logging
from typing import Tuple, Union

from quart import Blueprint, jsonify, request, current_app as app

from api.common.auth import token_check
from api.errors import BadInput

bp = Blueprint("list", __name__)
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


def construct_url(domain: str, url_basename: str, *, scope: str = "i") -> str:
    """Create an URL for the given object."""

    # http is allowed for local testing
    prefix = "https://" if app.econfig.USE_HTTPS else "http://"
    return f"{prefix}{domain}/{scope}/{url_basename}"


def _get_before_after() -> Tuple[Union[int, float], int]:
    before = request.args.get("before")
    if before is None:
        # NOTE the biggest value in int64 is this
        before = (1 << 63) - 1
    else:
        try:
            before = int(before)
        except ValueError:
            raise BadInput("Optional before parameter must be an integer")

    try:
        after = int(request.args.get("after") or 0)
    except ValueError:
        raise BadInput("Optional after parameter must be an integer")

    return before, after


@bp.route("/files")
async def list_files():
    """List user files"""
    before, after = _get_before_after()
    user_id = await token_check()
    domains = await domain_list()

    user_files = await app.db.fetch(
        """
        SELECT file_id, filename, file_size, fspath, mimetype, domain, subdomain
        FROM files
        WHERE uploader = $1
          AND deleted = false
          AND file_id < $2
          AND file_id > $3
        ORDER BY file_id DESC
        LIMIT 100
        """,
        user_id,
        before,
        after,
    )

    files = []

    for file_row in user_files:
        shortname = file_row["filename"]
        mime = file_row["mimetype"]

        # files *can* have subdomains for them (as of !58) so
        # we construct a domain based off the given file row
        domain = construct_domain(domains, file_row)

        # create file + extension as the urls require extensions
        basename = os.path.basename(file_row["fspath"])
        ext = basename.split(".")[-1]
        file_in_url = f"{shortname}.{ext}"
        file_url = construct_url(domain, file_in_url)

        file_object = {
            "id": str(file_row["file_id"]),
            "shortname": shortname,
            "size": file_row["file_size"],
            "mimetype": mime,
            "url": file_url,
        }

        # only images have thumbnails, and, by default, we give
        # the small thumbnail url for them while listing
        if mime.startswith("image/"):
            file_object["thumbnail"] = construct_url(domain, f"s{shortname}", scope="t")

        files.append(file_object)

    return jsonify({"files": files})


@bp.route("/shortens")
async def list_shortens():
    """List user shortens"""
    before, after = _get_before_after()
    user_id = await token_check()
    domains = await domain_list()

    user_shortens = await app.db.fetch(
        """
        SELECT shorten_id, filename, redirto, domain, subdomain
        FROM shortens
        WHERE uploader = $1
          AND deleted = false
          AND shorten_id < $2
          AND shorten_id > $3
        ORDER BY shorten_id DESC
        LIMIT 100
        """,
        user_id,
        before,
        after,
    )

    shortens = []
    # some of the things commented in /files also apply here
    # e.g subdomain (!58)

    for shorten in user_shortens:
        shortname = shorten["filename"]
        domain = construct_domain(domains, shorten)
        shorten_url = construct_url(domain, shortname, scope="s")

        shorten_obj = {
            "id": str(shorten["shorten_id"]),
            "shortname": shortname,
            "redirto": shorten["redirto"],
            "url": shorten_url,
        }

        shortens.append(shorten_obj)

    return jsonify({"shortens": shortens})
