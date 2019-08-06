# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import os
import time
from typing import Optional, Tuple

from quart import Blueprint, current_app as app, request, send_file

from PIL import Image

from api.errors import NotFound
from api.storage import StorageValue

bp = Blueprint("fetch", __name__)
log = logging.getLogger(__name__)


async def _get_fspath(
    *, shortname: str, domain_id: int, subdomain: Optional[str]
) -> StorageValue:
    """Return the path to a image (or other file) on disk."""

    # TODO: we still need to handle `subdomain == ''` for when the file lives
    #       on both a wildcard and the root domain (which is the case for v2
    #       files)

    if subdomain is None:
        # file lives on the root domain
        filepath = await app.storage.get_fspath(
            shortname=shortname, domain_id=domain_id
        )
        return filepath

    # file lives on the root domain
    filepath = await app.storage.get_fspath(
        shortname=shortname, domain_id=domain_id, subdomain=subdomain
    )

    return filepath


async def resolve_file(filename) -> Tuple[str, Optional[str]]:
    """Resolve a file according to its filename (shortname plus an extension).

    If the file doesn't exist, a :class:`NotFound` exception will be raised.
    Returns a tuple of the path to the file and an optional shortname.
    """
    domain_id, subdomain = await app.storage.get_domain_id(request.host)

    shortname, ext = os.path.splitext(filename)

    # resolve the path to this file on the filesystem from its shortname and
    # domain
    file_path = (
        await _get_fspath(shortname=shortname, domain_id=domain_id, subdomain=subdomain)
    ).value

    if not file_path:
        raise NotFound("No files with this name on this domain.")

    # If we don't do this, there's a tiny chance of someone uploading an .exe
    # with extension of .png or whatever and slipping through ClamAV
    # and then handing people the URL <domain>/<shortname>.exe.
    # Theoretically I could compare mime types but this works better IMO
    # as it prevents someone from uploading asd.jpg and linking asd.jpeg
    # and due to that, it makes cf cache revokes MUCH less painful
    db_ext = os.path.splitext(file_path)[-1]
    if db_ext != ext:
        raise NotFound("No files with this name on this domain.")

    return file_path, shortname


async def _send_file(fspath: str, mimetype: Optional[str] = None):
    resp = await send_file(fspath, mimetype=mimetype)
    resp.headers["content-security-policy"] = "sandbox; frame-src 'None'"
    return resp


@bp.route("/i/<filename>")
async def file_handler(filename):
    """Handles file serves."""
    filepath, shortname = await resolve_file(filename)

    # fetch the file's mimetype from the database
    # which should be way more reliable than sanic
    # taking a guess at it.
    mimetype = await app.storage.get_file_mime(shortname)

    if mimetype == "text/plain":
        mimetype = "text/plain; charset=utf-8"

    return await _send_file(filepath, mimetype)


@bp.route("/t/<filename>")
async def thumbnail_handler(filename):
    """Handles thumbnail serves."""
    appcfg = app.econfig
    thumbtype, filename = filename[0], filename[1:]
    fspath, _shortname = await resolve_file(filename)

    # if thumbnails are disabled, just return
    # the same file
    if not appcfg.THUMBNAILS:
        return await _send_file(fspath)

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
    return await _send_file(thumbpath)
