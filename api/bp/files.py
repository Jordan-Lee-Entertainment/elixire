import os
import logging

from sanic import Blueprint
from sanic import response

from ..common_auth import token_check
from ..errors import NotFound

bp = Blueprint('files')
log = logging.getLogger(__name__)


async def domain_list(request):
    """Returns a dictionary with domain IDs mapped to domain names"""
    domain_info = await request.app.db.fetch("""
        SELECT domain_id, domain
        FROM domains
    """)
    return dict(domain_info)


@bp.get('/api/list')
async def list_handler(request):
    """Get list of files."""
    user_id = await token_check(request)
    domains = await domain_list(request)

    user_files = await request.app.db.fetch("""
    SELECT fspath, domain
    FROM files
    WHERE uploader = $1
    AND deleted = false
    ORDER BY file_id DESC
    """, user_id)

    user_shortens = await request.app.db.fetch("""
    SELECT filename, redirto, domain
    FROM shortens
    WHERE uploader = $1
    AND deleted = false
    ORDER BY shorten_id DESC
    """, user_id)

    filenames = [f"https://{domains[ufile['domain']]}/i/"
                 f"{os.path.basename(ufile['fspath'])}" for ufile in user_files]

    shortens = [{f"https://{domains[ushorten['domain']]}/s/"
                 f"{ushorten['filename']}": ushorten["redirto"]}
                for ushorten in user_shortens]

    return response.json({
        'success': True,
        'files': filenames,
        'shortens': shortens
    })


async def purge_cf_cache(app, file_name: str, base_urls):
    """Clear the Cloudflare cache for the given URL."""

    if not app.econfig.CF_PURGE:
        log.warning('Cloudflare purging is disabled.')
        return

    cf_purge_url = "https://api.cloudflare.com/client/v4/zones/"\
                   f"{app.econfig.CF_ZONEID}/purge_cache"

    purge_urls = [file_url+file_name for file_url in base_urls]

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
    # TODO: Reduce code repetition between this and /api/shortendelete
    user_id = await token_check(request)
    file_name = str(request.json['filename'])

    exec_out = await request.app.db.execute("""
    UPDATE files
    SET deleted = true
    WHERE uploader = $1
    AND filename = $2
    AND deleted = false
    """, user_id, file_name)

    if exec_out == "UPDATE 0":
        raise NotFound('You have no files with this name.')

    # Checking if purge is enabled here too
    # So we can prevent an extra API call if it is not necessary
    if request.app.econfig.CF_PURGE:
        file_path = await request.app.db.fetchval("""
        SELECT fspath
        FROM files
        WHERE filename = $1
        AND deleted = true
        """, file_name)

        full_filename = os.path.basename(file_path)

        await purge_cf_cache(request.app, full_filename,
                             request.app.econfig.CF_UPLOADURLS)

    return response.json({
        'success': True
    })


@bp.delete('/api/shortendelete')
async def shortendelete_handler(request):
    """Invalidate a shorten."""
    user_id = await token_check(request)
    file_name = str(request.json['filename'])

    exec_out = await request.app.db.execute("""
    UPDATE shortens
    SET deleted = true
    WHERE uploader = $1
    AND filename = $2
    AND deleted = false
    """, user_id, file_name)

    # By doing this, we're cutting down DB calls by half
    # and it still checks for user
    if exec_out == "UPDATE 0":
        raise NotFound('You have no shortens with this name.')

    await purge_cf_cache(request.app, file_name,
                         request.app.econfig.CF_SHORTENURLS)

    return response.json({
        'success': True
    })
