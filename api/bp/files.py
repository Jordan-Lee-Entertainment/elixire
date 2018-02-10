from sanic import Blueprint
from sanic import response

from ..common_auth import token_check
from ..errors import FailedAuth

bp = Blueprint('files')


@bp.get('/api/list')
async def list_handler(request):
    # TODO
    pass


@bp.get('/api/delete')
async def delete_handler(request):
    """Invalidate a file."""
    # NOTE: this is NOT tested
    user_id = await token_check(request)
    file_name = str(request.json['filename'])

    uploader_id = await request.app.db.fetchval("""
    SELECT uploader
    FROM files
    WHERE filename = $1
    """, file_name)

    if uploader_id != user_id:
        raise FailedAuth('You are not the uploader of this file.')

    await request.app.db.execute("""
    UPDATE files
    SET deleted=true
    WHERE filename=$1
    """, file_name)

    # TODO: invalidate cloudflare
    # TODO: invalidate our handler so it raises 404
    #    I really don't know how we should do this
    #    since we use .add_static from ./images to /i.
    #     in theory we could move the image to
    #     another folder and .add_static would 404
    #     it automatically.

    return response.json({
        'success': True
    })
