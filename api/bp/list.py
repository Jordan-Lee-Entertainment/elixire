# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import Tuple, Union

from quart import Blueprint, jsonify, request, current_app as app

from api.common.auth import token_check
from api.models import File
from api.common.pagination import lazy_paginate

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


@bp.route("/files")
async def list_files():
    """List user files"""
    before, after, limit = lazy_paginate()
    user_id = await token_check()

    user_files = await app.db.fetch(
        """
        SELECT file_id, mimetype, filename, file_size, uploader, fspath,
               deleted, domain, subdomain
        FROM files
        WHERE uploader = $1
          AND deleted = false
          AND file_id < $2
          AND file_id > $3
        ORDER BY file_id DESC
        LIMIT $4
        """,
        user_id,
        before,
        after,
        limit,
    )

    elixire_files = [File(file_row) for file_row in user_files]
    urls = await File.construct_urls(elixire_files)

    files = []

    for index, elixire_file in enumerate(elixire_files):
        file_urls = urls[index]
        files.append({**elixire_file.to_dict(public=True), **file_urls})

    return jsonify({"files": files})


@bp.route("/shortens")
async def list_shortens():
    """List user shortens"""
    before, after, limit = lazy_paginate()
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
        LIMIT $4
        """,
        user_id,
        before,
        after,
        limit,
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
