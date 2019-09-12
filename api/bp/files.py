# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import logging

from quart import Blueprint, jsonify, request, current_app as app

from api.common import delete_file, delete_shorten
from api.common.auth import token_check, password_check
from api.errors import BadInput

from api.common.user import mass_file_delete

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


@bp.route("/files/delete_all", methods=["POST"])
async def delete_all():
    """Delete all files for the user"""
    user_id = await token_check()

    j = await request.get_json()

    try:
        password = j["password"]
    except KeyError:
        raise BadInput("password not provided")

    await password_check(user_id, password)

    task_name = f"delete_files_{user_id}"
    if app.sched.exists(task_name):
        return (
            jsonify({"error": True, "message": "background task already running"}),
            409,
        )

    # create task to delete all files in the background
    app.sched.spawn(mass_file_delete(user_id, False), task_name)
    return "", 204


@bp.route("/files/<shortname>", methods=["DELETE"])
@bp.route("/files/<shortname>/delete", methods=["GET"])
async def delete_single(shortname):
    """Delete a single file."""
    user_id = await token_check()
    await delete_file(shortname, user_id)
    return "", 204


@bp.route("/shortens/<shorten_name>", methods=["DELETE"])
async def shortendelete_handler(user_id, shorten_name):
    """Invalidate a shorten."""
    user_id = await token_check()
    await delete_shorten(shorten_name, user_id)
    return "", 204
