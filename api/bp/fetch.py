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

    return filepath


@bp.get('/i/<filename>')
async def file_handler(request, filename):
    """Handles file serves."""
    filepath = await filecheck(request, filename)
    return await response.file(filepath, headers={"Content-Security-Policy":
                                                  "script-src 'none'"})


@bp.get('/t/<filename>')
async def thumbnail_handler(request, filename):
    """Handles thumbnail serves."""
    appcfg = request.app.econfig
    thumbtype, filename = filename[0], filename[1:]
    fspath = await filecheck(request, filename)

    if not appcfg.THUMBNAILS:
        return await response.file(fspath)

    thb_folder = appcfg.THUMBNAIL_FOLDER
    thumbpath = os.path.join(thb_folder, f'{thumbtype}{filename}')

    if not os.path.isfile(thumbpath):
        # call pillow, make it
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
    return await response.file(thumbpath, headers={"Content-Security-Policy":
                                                   "script-src 'none'"})
