# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import os
import time
from typing import Optional, Tuple

from quart import Blueprint, current_app as app, request, redirect
from api.common.utils import send_file

from PIL import Image

from api.errors import NotFound
from api.storage import StorageValue

bp = Blueprint("fetch", __name__)
log = logging.getLogger(__name__)


async def _get_fspath(
    *, shortname: str, domain_id: int, subdomain: str
) -> StorageValue:
    """Return the path to a image (or other file) on disk."""

    # when searching for the file, the subdomain can be applicable
    # or NOT while searching. which means that when we're searching with it,
    # if it fails, we MUST search with subdomain=None. that only happens for
    # legacy files that have subdomain as NULL on the database.

    # for files uploaded as root, the subdomain becomes "" (empty string)
    # which is completly valid to put on the search.
    filepath = await app.storage.get_fspath(
        shortname=shortname, domain_id=domain_id, subdomain=subdomain
    )

    if not filepath:
        filepath = await app.storage.get_fspath(
            shortname=shortname, domain_id=domain_id, subdomain=None
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

    return await send_file(filepath, mimetype=mimetype)


@bp.route("/t/<filename>")
async def thumbnail_handler(filename):
    """Handles thumbnail serves."""
    appcfg = app.econfig
    thumbtype, filename = filename[0], filename[1:]
    fspath, _shortname = await resolve_file(filename)

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


async def _get_urlredir(
    *, shortname: str, domain_id: str, subdomain: str
) -> StorageValue:
    """Return the target URL (``toredir``) for a shorten."""

    # NOTE this is a copy from the internal _get_fspath
    # function in api.bp.fetch.

    # when searching for the file, the subdomain can be applicable
    # or NOT while searching. which means that when we're searching with it,
    # if it fails, we MUST search with subdomain=None. that only happens for
    # legacy files that have subdomain as NULL on the database.

    # for shortens uploaded as root, the subdomain becomes "" (empty string)
    # which is completly valid to put on the search.
    url_toredir = await app.storage.get_urlredir(
        shortname=shortname, domain_id=domain_id, subdomain=subdomain
    )

    if not url_toredir:
        url_toredir = await app.storage.get_urlredir(
            shortname=shortname, domain_id=domain_id, subdomain=None
        )

    return url_toredir


@bp.route("/s/<shortname>")
async def shorten_serve_handler(shortname):
    """Handles serving of shortened links."""
    storage = app.storage

    domain_id, subdomain = await storage.get_domain_id(request.host)
    url_toredir = (
        await _get_urlredir(
            shortname=shortname, domain_id=domain_id, subdomain=subdomain
        )
    ).value

    if not url_toredir:
        raise NotFound("No shortened links found with this name on this domain.")

    return redirect(url_toredir)
