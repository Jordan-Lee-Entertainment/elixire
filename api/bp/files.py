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

    # oh god this mess
    shortens = dict([(f"https://{domains[ushorten['domain']]}/s/"
                      f"{ushorten['filename']}", ushorten["redirto"])
                     for ushorten in user_shortens])

    return response.json({
        'success': True,
        'files': filenames,
        'shortens': shortens
    })


async def _purge_cf_cache(app, purge_urls, email, apikey, zoneid):
    """Clear the Cloudflare cache for the given URLs and cf creds."""

    cf_purge_url = "https://api.cloudflare.com/client/v4/zones/"\
                   f"{zoneid}/purge_cache"

    cf_auth_headers = {
        'X-Auth-Email': email,
        'X-Auth-Key': apikey
    }

    purge_payload = {
        'files': purge_urls,
    }

    async with app.session.delete(cf_purge_url,
                                  json=purge_payload,
                                  headers=cf_auth_headers) as resp:
        return resp


# TODO: I tried, I really tried, but i can't seem to reduce the code
# repetition with the following two functions without adding more DB calls
# and I don't want even more DB calls
async def purge_cf_cache_file(app, filename: str):
    file_detail = await app.db.fetchrow("""
    SELECT domain, fspath
    FROM files
    WHERE filename = $1
    """, filename)

    domain_detail = await app.db.fetchrow("""
    SELECT domain, cf_enabled, cf_email, cf_zoneid, cf_apikey
    FROM domains
    WHERE domain_id = $1
    """, file_detail["domain"])

    # Checking if purge is enabled
    if domain_detail["cf_enabled"]:
        purge_url = f"https://{domain_detail['domain']}/i/"\
                    f"{os.path.basename(file_detail['fspath'])}"

        await _purge_cf_cache(app, [purge_url], domain_detail["cf_email"],
                              domain_detail["cf_apikey"],
                              domain_detail["cf_zoneid"])


async def purge_cf_cache_shorten(app, filename: str):
    shorten_detail = await app.db.fetchval("""
    SELECT domain
    FROM shortens
    WHERE filename = $1
    """, filename)

    domain_detail = await app.db.fetchrow("""
    SELECT domain, cf_enabled, cf_email, cf_zoneid, cf_apikey
    FROM domains
    WHERE domain_id = $1
    """, shorten_detail["domain"])

    # Checking if purge is enabled
    if domain_detail["cf_enabled"]:
        purge_url = f"https://{domain_detail['domain']}/s/{filename}"

        await _purge_cf_cache(app, [purge_url], domain_detail["cf_email"],
                              domain_detail["cf_apikey"],
                              domain_detail["cf_zoneid"])


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

    await purge_cf_cache_file(request.app, file_name)

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

    await purge_cf_cache_shorten(request.app, file_name)

    return response.json({
        'success': True
    })
