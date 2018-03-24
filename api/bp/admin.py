"""
elixire - admin routes
"""

from sanic import Blueprint, response

from ..common_auth import login_user, check_admin
from ..errors import NotFound, BadInput


bp = Blueprint('admin')


@bp.get('/api/admin/test')
async def test_admin(request):
    """Get a json payload for admin users.

    This is just a test route.
    """
    user = await login_user(request)
    await check_admin(user['id'], True)

    return response.json({
        'admin': True
    })


@bp.get('/api/admin/users')
async def list_users_handler(request):
    user = await login_user(request)
    await check_admin(user['id'], True)

    try:
        page = request.json['page']
    except (ValueError, TypeError):
        raise BadInput('invalid page value')

    # TODO: paging.
    page = await request.app.db.fetchr("""
    SELECT *
    FROM users
    LIMIT 1
    """)

    return request.json(list(map(dict, page)))


@bp.get('/api/admin/users/<user_id:int>')
async def get_user_handler(request, user_id):
    user = await login_user(request)
    await check_admin(user['id'], True)

    udata = await request.app.db.fetchrow("""
    SELECT *
    FROM users
    WHERE user_id=$1
    """, user_id)

    if not udata:
        raise NotFound('User not found')

    return response.json(dict(udata))
