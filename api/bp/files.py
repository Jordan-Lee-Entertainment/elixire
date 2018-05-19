import os
import logging

from sanic import Blueprint
from sanic import response

from ..common import purge_cf, FileNameType
from ..common_auth import token_check
from ..errors import NotFound, BadInput

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
    try:
        print(request.args)
        page = int(request.args['page'][0])
    except (TypeError, ValueError, KeyError, IndexError):
        raise BadInput('Page parameter needs to be supplied correctly.')

    user_id = await token_check(request)
    domains = await domain_list(request)

    user_files = await request.app.db.fetch("""
    SELECT file_id, filename, file_size, fspath, domain
    FROM files
    WHERE uploader = $1
    AND deleted = false
    ORDER BY file_id DESC

    LIMIT 100
    OFFSET ($2 * 100)
    """, user_id, page)

    user_shortens = await request.app.db.fetch("""
    SELECT shorten_id, filename, redirto, domain
    FROM shortens
    WHERE uploader = $1
    AND deleted = false
    ORDER BY shorten_id DESC

    LIMIT 100
    OFFSET ($2 * 100)
    """, user_id, page)

    filenames = {}
    for ufile in user_files:
        filename = ufile['filename']
        domain = domains[ufile['domain']].replace("*.", "wildcard.")
        basename = os.path.basename(ufile['fspath'])

        file_url = f'https://{domain}/i/{basename}'

        use_https = request.app.econfig.USE_HTTPS
        prefix = 'https://' if use_https else 'http://'
        file_url_thumb = f'{prefix}{domain}/t/s{basename}'

        filenames[filename] = {
            'snowflake': ufile['file_id'],
            'shortname': filename,
            'size': ufile['file_size'],

            'url': file_url,
            'thumbnail': file_url_thumb,
        }

    shortens = {}
    for ushorten in user_shortens:
        filename = ushorten['filename']
        domain = domains[ushorten['domain']]

        use_https = request.app.econfig.USE_HTTPS
        prefix = 'https://' if use_https else 'http://'
        shorten_url = f'{prefix}{domain}/s/{filename}'

        shortens[filename] = {
            'snowflake': ushorten['shorten_id'],
            'shortname': filename,
            'redirto': ushorten['redirto'],
            'url': shorten_url,
        }

    return response.json({
        'success': True,
        'files': filenames,
        'shortens': shortens
    })


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

    domain_id = await purge_cf(request.app, file_name, FileNameType.FILE)
    await request.app.storage.raw_invalidate(f'fspath:{domain_id}:{file_name}')

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

    domain_id = await purge_cf(request.app, file_name, FileNameType.SHORTEN)
    await request.app.storage.raw_invalidate(f'redir:{domain_id}:{file_name}')

    return response.json({
        'success': True
    })
