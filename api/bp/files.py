# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import logging

from quart import Blueprint, current_app as app, jsonify, request
from quart.ctx import copy_current_app_context

from ..common import delete_file, delete_shorten
from ..common.auth import token_check, password_check
from ..decorators import auth_route
from ..errors import BadInput
from .profile import delete_file_task

bp = Blueprint("files", __name__)
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


@bp.get("/list")
async def list_handler():
    """Get list of files."""
    # TODO: simplify this code
    try:
        page = int(request.args["page"][0])
    except (TypeError, ValueError, KeyError, IndexError):
        raise BadInput("Page parameter needs to be supplied correctly.")

    user_id = await token_check()
    domains = await domain_list()

    user_files = await app.db.fetch(
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

    user_shortens = await app.db.fetch(
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

    use_https = app.econfig.USE_HTTPS
    prefix = "https://" if use_https else "http://"

    filenames = {}
    for ufile in user_files:
        filename = ufile["filename"]
        mime = ufile["mimetype"]
        domain = domains[ufile["domain"]].replace("*.", "wildcard.")

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
        domain = domains[ushorten["domain"]].replace("*.", "wildcard.")

        shorten_url = f"{prefix}{domain}/s/{filename}"

        shortens[filename] = {
            "snowflake": str(ushorten["shorten_id"]),
            "shortname": filename,
            "redirto": ushorten["redirto"],
            "url": shorten_url,
        }

    return jsonify({"success": True, "files": filenames, "shortens": shortens})


@bp.delete("/delete")
async def delete_handler():
    """Invalidate a file."""
    user_id = await token_check()
    # TODO validation
    j = await request.get_json()
    file_name = str(j["filename"])

    await delete_file(file_name, user_id)

    return jsonify({"success": True})


@bp.post("/delete_all")
@auth_route
async def delete_all(user_id):
    """Delete all files for the user"""

    j = await request.get_json()

    try:
        password = j["password"]
    except KeyError:
        raise BadInput("password not provided")

    await password_check(user_id, password)

    # create task to delete all files in the background
    @copy_current_app_context
    async def _wrap(*args):
        await delete_file_task(*args)

    app.sched.spawn(_wrap(user_id, False), f"delete_files_{user_id}")

    return jsonify(
        {
            "success": True,
        }
    )


@bp.route("/delete/<shortname>", methods=["GET", "DELETE"])
@auth_route
async def delete_single(user_id, shortname):
    await delete_file(shortname, user_id)
    return jsonify({"success": True})


@bp.delete("/shortendelete")
async def shortendelete_handler():
    """Invalidate a shorten."""
    user_id = await token_check()
    j = await request.get_json()
    file_name = str(j["filename"])

    await delete_shorten(file_name, user_id)

    return jsonify({"success": True})
