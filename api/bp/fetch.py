# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import os
import time

from sanic import Blueprint
from sanic import response

from PIL import Image

from ..errors import NotFound

bp = Blueprint('fetch')
log = logging.getLogger(__name__)


async def filecheck(request, filename):
    """Check if the given file exists on the domain."""
    storage = request.app.storage
    domain_id = await storage.get_domain_id(request.host)

    shortname, ext = os.path.splitext(filename)

    filepath = await storage.get_fspath(shortname, domain_id)
    if not filepath:
        raise NotFound('No files with this name on this domain.')

    # If we don't do this, there's a tiny chance of someone uploading an .exe
    # with extension of .png or whatever and slipping through ClamAV
    # and then handing people the URL <domain>/<shortname>.exe.
    # Theoretically I could compare mime types but this works better IMO
    # as it prevents someone from uploading asd.jpg and linking asd.jpeg
    # and due to that, it makes cf cache revokes MUCH less painful
    db_ext = os.path.splitext(filepath)[-1]
    if db_ext != ext:
        raise NotFound('No files with this name on this domain.')

    return filepath, shortname


@bp.get('/i/<filename>')
async def file_handler(request, filename):
    """Handles file serves."""
    # Account for requests from Discord to preserve URL
    # TODO: maybe give this a separate func and also call from thumbs?
    is_raw = request.args.get("raw")
    is_discordbot = "Discordbot" in request.headers.get("User-Agent", "")

    if is_discordbot and not is_raw:
        # Generate a ?raw=true URL
        # Use & if there's already a query string
        raw_url = (request.url
                   + ("&" if request.query_string else "?")
                   + "raw=true")

        return response.html("""
<html>
    <head>
        <meta property="twitter:card" content="summary_large_image">
        <meta property="twitter:image" content="{}">
    </head>
</html>""".format(raw_url))

    app = request.app
    filepath, shortname = await filecheck(request, filename)

    # fetch the file's mimetype from the database
    # which should be way more reliable than sanic
    # taking a guess at it.
    mimetype = await app.storage.get_file_mime(shortname)

    if mimetype == 'text/plain':
        mimetype = 'text/plain; charset=utf-8'

    return await response.file_stream(
        filepath,
        headers={
            'Content-Security-Policy': "sandbox; frame-src 'none'"
        },
        mime_type=mimetype)


@bp.get('/t/<filename>')
async def thumbnail_handler(request, filename):
    """Handles thumbnail serves."""
    appcfg = request.app.econfig
    thumbtype, filename = filename[0], filename[1:]
    fspath, _shortname = await filecheck(request, filename)

    # if thumbnails are disabled, just return
    # the same file
    if not appcfg.THUMBNAILS:
        return await response.file_stream(fspath)

    thb_folder = appcfg.THUMBNAIL_FOLDER
    thumbpath = os.path.join(thb_folder, f'{thumbtype}{filename}')

    if not os.path.isfile(thumbpath):
        tstart = time.monotonic()

        image = Image.open(fspath)
        image.thumbnail(appcfg.THUMBNAIL_SIZES[thumbtype])
        image.save(thumbpath)

        tend = time.monotonic()
        delta = round((tend - tstart) * 1000, 5)
        log.info(f'Took {delta} msec generating thumbnail '
                 f'type {thumbtype} for {filename}')

    # yes, we are doing more I/O by using response.file
    # and not sending the bytes ourselves.
    return await response.file_stream(
        thumbpath,
        headers={
            'Content-Security-Policy': "sandbox; frame-src 'none'"
        })
