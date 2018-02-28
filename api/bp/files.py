import os
import logging

from sanic import Blueprint
from sanic import response

from ..common_auth import token_check
from ..errors import NotFound

bp = Blueprint('files')
log = logging.getLogger(__name__)


@bp.get('/api/list')
async def list_handler(request):
    """Get list of files."""
    user_id = await token_check(request)

    user_files = await request.app.db.fetch("""
    SELECT fspath
    FROM files
    WHERE uploader = $1
    AND deleted = false
    ORDER BY file_id DESC
    """, user_id)

    filenames = [os.path.basename(ufile['fspath']) for ufile in user_files]

    return response.json({
        'success': True,
        'files': filenames
    })


async def purge_cf_cache(app, file_name: str):
    """Clear the Cloudflare cache for the given URL."""

    if not app.econfig.CF_PURGE:
        log.warning('Cloudflare purging is disabled.')
        return

    cf_purge_url = "https://api.cloudflare.com/client/v4/zones/"\
                   f"{app.econfig.CF_ZONEID}/purge_cache"

    purge_urls = [file_url+file_name for file_url in app.econfig.CF_UPLOADURLS]

    cf_auth_headers = {
        'X-Auth-Email': app.econfig.CF_EMAIL,
        'X-Auth-Key': app.econfig.CF_APIKEY
    }

    purge_payload = {
        'files': purge_urls,
    }

    async with app.session.delete(cf_purge_url,
                                  json=purge_payload,
                                  headers=cf_auth_headers) as resp:
        return resp


@bp.delete('/api/delete')
async def delete_handler(request):
    """Invalidate a file."""
    user_id = await token_check(request)
    file_name = str(request.json['filename'])

    file_info = await request.app.db.fetchrow("""
    SELECT uploader, fspath
    FROM files
    WHERE filename = $1
    AND deleted = false
    """, file_name)

    if not file_info or file_info["uploader"] != user_id:
        raise NotFound('You have no files with this name.')

    full_filename = os.path.basename(file_info['fspath'])
    new_path = f"./deleted/{full_filename}"

    os.rename(file_info["fspath"], new_path)

    await request.app.db.execute("""
    UPDATE files
    SET deleted = true, fspath = $1
    WHERE filename = $2
    """, new_path, file_name)

    await purge_cf_cache(request.app, full_filename)

    return response.json({
        'success': True
    })
