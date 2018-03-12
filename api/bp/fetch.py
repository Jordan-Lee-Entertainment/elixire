import logging
import os

from sanic import Blueprint
from sanic import response

from ..errors import NotFound
from ..common_auth import check_domain

bp = Blueprint('fetch')
log = logging.getLogger(__name__)


@bp.get('/i/<filename>')
async def file_handler(request, filename):
    """Handles file serves."""
    domain = await check_domain(request, request.host)

    shortname, ext = os.path.splitext(filename)

    filepath = await request.app.db.fetchval("""
    SELECT fspath
    FROM files
    WHERE filename = $1
    AND deleted = false
    AND domain = $2
    """, shortname, domain["domain_id"])

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

    return await response.file(filepath)
