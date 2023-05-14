# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only


import logging

from quart import Blueprint, current_app as app, jsonify, request
from pathlib import Path

from ..common.auth import token_check
from ..common.utils import service_url
from ..errors import BadInput


bp = Blueprint("list", __name__)
log = logging.getLogger(__name__)


async def domain_list():
    """Returns a dictionary with domain IDs mapped to domain names"""
    domain_info = await app.db.fetch(
        """
        SELECT domain_id, domain
        FROM domains
    """
    )
    return dict(domain_info)


def web_domain_from_entity(domains: dict, entity: dict) -> str:
    """Construct a full domain, given the list of domains and the object to
    put subdomains on. the default is "wildcard"."""
    domain = domains[entity["domain"]]
    if domain.startswith("*."):
        domain = domain.replace("*", "wildcard")

    return domain


def create_entity_url(domain: str, url_basename: str, *, scope: str = "i") -> str:
    """Create an URL for the given object."""
    return service_url(domain, f"/{scope}/{url_basename}")


def file_from_row(domains: dict, row: dict) -> dict:
    domain = web_domain_from_entity(domains, row)
    suffix = Path(row["fspath"]).suffix

    filename = row["filename"]
    image_web_path = f"{filename}{suffix}"
    file_url = create_entity_url(domain, image_web_path, scope="i")

    mimetype = row["mimetype"]
    thumbnail_url = (
        create_entity_url(domain, f"s{image_web_path}", scope="t")
        if mimetype.startswith("image/")
        else file_url
    )

    return {
        "snowflake": str(row["file_id"]),
        "shortname": filename,
        "size": row["file_size"],
        "mimetype": mimetype,
        "url": file_url,
        "thumbnail": thumbnail_url,
    }


def shorten_from_row(domains, row) -> dict:
    domain = web_domain_from_entity(domains, row)
    filename = row["filename"]
    shorten_url = create_entity_url(domain, filename, scope="s")
    return {
        "snowflake": str(row["shorten_id"]),
        "shortname": filename,
        "redirto": row["redirto"],
        "url": shorten_url,
    }


@bp.get("/list")
async def list_handler():
    """Get list of files."""
    try:
        page = int(request.args["page"][0])
    except (TypeError, ValueError, KeyError, IndexError):
        raise BadInput("Invalid page parameter.")

    user_id = await token_check()
    domains = await domain_list()

    file_rows = await app.db.fetch(
        """
    SELECT file_id, filename, file_size, fspath, domain, mimetype
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

    shorten_rows = await app.db.fetch(
        """
    SELECT shorten_id, filename, redirto, domain
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

    files = {}
    for row in file_rows:
        files[row["filename"]] = file_from_row(domains, row)

    shortens = {}
    for row in shorten_rows:
        shortens[row["filename"]] = shorten_from_row(domains, row)

    return jsonify({"success": True, "files": files, "shortens": shortens})
