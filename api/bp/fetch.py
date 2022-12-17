# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import os
import time
from typing import Optional

from quart import (
    Blueprint,
    current_app as app,
    request,
    send_file as quart_send_file,
)

from PIL import Image

from ..errors import NotFound
from ..common.utils import service_url

bp = Blueprint("fetch", __name__)
log = logging.getLogger(__name__)


async def filecheck(filename):
    """Check if the given file exists on the domain."""
    storage = app.storage
    domain_id = await storage.get_domain_id(request.host)

    shortname, ext = os.path.splitext(filename)

    filepath = await storage.get_fspath(shortname, domain_id)
    if not filepath:
        raise NotFound("No files with this name on this domain.")

    # If we don't do this, there's a tiny chance of someone uploading an .exe
    # with extension of .png or whatever and slipping through ClamAV
    # and then handing people the URL <domain>/<shortname>.exe.
    # Theoretically I could compare mime types but this works better IMO
    # as it prevents someone from uploading asd.jpg and linking asd.jpeg
    # and due to that, it makes cf cache revokes MUCH less painful
    db_ext = os.path.splitext(filepath)[-1]
    if db_ext != ext:
        raise NotFound("No files with this name on this domain.")

    return filepath, shortname


async def send_file(
    path: str, *, mimetype: Optional[str] = None, domain: Optional[str] = None
):
    """Helper function to send files while also supporting Ranged Requests."""
    domain = domain or app._root_domain
    response = await quart_send_file(path, mimetype=mimetype, conditional=True)

    filebody = response.response
    response.headers["content-length"] = filebody.end - filebody.begin
    response.headers["content-disposition"] = "inline"
    response.headers["content-security-policy"] = "sandbox; frame-src 'None'"
    response.headers["Access-Control-Allow-Origin"] = domain

    return response


@bp.get("/i/<filename>")
async def file_handler(filename):
    """Handles file serves."""

    # validate that the file exists before doing any further processing
    # this is done before discordbot user agent validation so that discord
    # doesn't attempt to load the url first, see that it has an embed,
    # and then when it tries to refetch with ?raw=1, it fails as the file
    # does not exist.
    #
    # by the end, you'd get a confusing embed that is empty inside the client.
    filepath, shortname = await filecheck(filename)

    # Account for requests from Discord to preserve URL
    # TODO: maybe give this a separate func and also call from thumbs?
    is_raw = request.args.get("raw")
    is_discordbot = "Discordbot" in request.headers.get("User-Agent", "")
    is_image = os.path.splitext(request.path)[-1].lower() in [
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    ]

    if is_discordbot and is_image and not is_raw:
        # Generate a ?raw=true URL
        # Use & if there's already a query string
        raw_url = (
            service_url(request.host, request.path)
            + ("&" if request.args else "?")
            + "raw=true"
        )

        return (
            """
<html>
    <head>
        <meta property="twitter:card" content="summary_large_image">
        <meta property="twitter:image" content="{}">
    </head>
</html>""".format(
                raw_url
            ),
            200,
            {"Content-Type": "text/html"},
        )

    # fetch the file's mimetype from the database
    # which should be way more reliable than sanic
    # taking a guess at it.
    mimetype = await app.storage.get_file_mime(shortname)

    if mimetype == "text/plain":
        mimetype = "text/plain; charset=utf-8"

    return await send_file(filepath, mimetype=mimetype, domain=request.host)


@bp.get("/t/<filename>")
async def thumbnail_handler(filename):
    """Handles thumbnail serves."""
    appcfg = app.econfig
    thumbtype, filename = filename[0], filename[1:]
    fspath, _shortname = await filecheck(filename)

    # if thumbnails are disabled, just return
    # the same file
    if not appcfg.THUMBNAILS:
        return await send_file(fspath)

    thb_folder = appcfg.THUMBNAIL_FOLDER
    thumbpath = os.path.join(thb_folder, f"{thumbtype}{filename}")

    if not os.path.isfile(thumbpath):
        tstart = time.monotonic()

        image = Image.open(fspath)
        image.thumbnail(appcfg.THUMBNAIL_SIZES[thumbtype])
        image.save(thumbpath)

        tend = time.monotonic()
        delta = round((tend - tstart) * 1000, 5)
        log.info(
            f"Took {delta} msec generating thumbnail "
            f"type {thumbtype} for {filename}"
        )

    # yes, we are doing more I/O by using response.file
    # and not sending the bytes ourselves.
    return await send_file(thumbpath)
