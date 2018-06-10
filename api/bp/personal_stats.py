import logging

from sanic import Blueprint
from sanic import response

from ..decorators import auth_route


bp = Blueprint('personal_stats')
log = logging.getLogger(__name__)


async def _get_counts(conn, table: str, user_id: int, extra: str = '') -> int:
    return await conn.fetchval(f"""
    SELECT COUNT(*)
    FROM {table}
    WHERE uploader = $1
    {extra}
    """, user_id)


@bp.get('/api/stats')
@auth_route
async def personal_stats_handler(request, user_id):
    """Personal statistics for users.
    """

    db = request.app.db

    total_files = await _get_counts(db, 'files', user_id)
    total_shortens = await _get_counts(db, 'shortens', user_id)
    total_deleted = await _get_counts(db, 'files', user_id,
                                      'AND deleted = true')

    total_bytes = await db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    """, user_id)

    return response.json({
        'total_files': total_files,
        'total_deleted_files': total_deleted,
        'total_bytes': total_bytes,
        'total_shortens': total_shortens,
    })
