import os
import logging

from sanic import Blueprint
from sanic import response

from ..common import delete_file, delete_shorten
from ..common.auth import token_check, password_check
from ..decorators import auth_route
from ..errors import BadInput
from .profile import delete_file_task

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
    # TODO: simplify this code
    try:
        page = int(request.args['page'][0])
    except (TypeError, ValueError, KeyError, IndexError):
        raise BadInput('Page parameter needs to be supplied correctly.')

    user_id = await token_check(request)
    domains = await domain_list(request)

    user_files = await request.app.db.fetch("""
    SELECT file_id, filename, file_size, fspath, domain, mimetype
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

    use_https = request.app.econfig.USE_HTTPS
    prefix = 'https://' if use_https else 'http://'

    filenames = {}
    for ufile in user_files:
        filename = ufile['filename']
        mime = ufile['mimetype']
        domain = domains[ufile['domain']].replace("*.", "wildcard.")

        basename = os.path.basename(ufile['fspath'])
        ext = basename.split('.')[-1]

        fullname = f'{filename}.{ext}'
        file_url = f'{prefix}{domain}/i/{fullname}'

        # default thumb size is small
        file_url_thumb = f'{prefix}{domain}/t/s{fullname}' \
                         if mime.startswith('image/') \
                         else file_url

        filenames[filename] = {
            'snowflake': str(ufile['file_id']),
            'shortname': filename,
            'size': ufile['file_size'],
            'mimetype': mime,

            'url': file_url,
            'thumbnail': file_url_thumb,
        }

    shortens = {}
    for ushorten in user_shortens:
        filename = ushorten['filename']
        domain = domains[ushorten['domain']].replace("*.", "wildcard.")

        shorten_url = f'{prefix}{domain}/s/{filename}'

        shortens[filename] = {
            'snowflake': str(ushorten['shorten_id']),
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
    user_id = await token_check(request)
    file_name = str(request.json['filename'])

    await delete_file(request.app, file_name, user_id)

    return response.json({
        'success': True
    })


@bp.post('/api/delete_all')
@auth_route
async def delete_all(request, user_id):
    """Delete all files for the user"""
    app = request.app

    try:
        password = request.json['password']
    except KeyError:
        raise BadInput('password not provided')

    await password_check(request, user_id, password)

    # create task to delete all files in the background
    app.loop.create_task(delete_file_task(app, user_id, False))

    return response.json({
        'success': True,
    })


@bp.route('/api/delete/<shortname>', methods=['GET', 'DELETE'])
@auth_route
async def delete_single(request, user_id, shortname):
    await delete_file(request.app, shortname, user_id)
    return response.json({
        'success': True
    })


@bp.delete('/api/shortendelete')
async def shortendelete_handler(request):
    """Invalidate a shorten."""
    user_id = await token_check(request)
    file_name = str(request.json['filename'])

    await delete_shorten(request.app, file_name, user_id)

    return response.json({
        'success': True
    })
