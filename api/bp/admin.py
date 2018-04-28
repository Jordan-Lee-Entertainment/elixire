"""
elixire - admin routes
"""

from sanic import Blueprint, response

from ..common_auth import token_check, check_admin
from ..errors import NotFound


bp = Blueprint('admin')


@bp.get('/api/admin/test')
async def test_admin(request):
    """Get a json payload for admin users.

    This is just a test route.
    """
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    return response.json({
        'admin': True
    })


@bp.get('/api/admin/users')
async def list_users_handler(request):
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    # TODO: this is inefficient.
    # how to approach paging, in something like SQL?
    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain
    FROM users
    """)

    return response.json(list(map(dict, data)))


@bp.get('/api/admin/users/<user_id:int>')
async def get_user_handler(request, user_id):
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    udata = await request.app.db.fetchrow("""
    SELECT user_id, suername, active, admin, domain
    FROM users
    WHERE user_id=$1
    """, user_id)

    if not udata:
        raise NotFound('User not found')

    return response.json(dict(udata))
