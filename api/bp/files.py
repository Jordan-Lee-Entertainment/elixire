import os
import logging

from sanic import Blueprint
from sanic import response

from ..common import purge_cf, FileNameType
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
    SELECT file_id, filename, file_size, fspath, domain
    FROM files
    WHERE uploader = $1
    AND deleted = false
    ORDER BY file_id DESC
    """, user_id)

    user_shortens = await request.app.db.fetch("""
    SELECT shorten_id, filename, redirto, domain
    FROM shortens
    WHERE uploader = $1
    AND deleted = false
    ORDER BY shorten_id DESC
    """, user_id)

    filenames = dict([(ufile["filename"],
                       {"snowflake": ufile["file_id"],
                        "shortname": ufile["filename"],
                        "size": ufile["file_size"],
                        "url": f"https://{domains[ufile['domain']]}/i/"
                        f"{os.path.basename(ufile['fspath'])}"}
                       ) for ufile in user_files])

    shortens = dict([(ushorten["filename"],
                      {"snowflake": ushorten["shorten_id"],
                       "shortname": ushorten["filename"],
                       "redirto": ushorten["redirto"],
                       "url": f"https://{domains[ushorten['domain']]}/s/"
                       f"{ushorten['filename']}"}
                      ) for ushorten in user_shortens])

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
