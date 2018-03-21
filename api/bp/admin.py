"""
elixire - admin routes
"""

from sanic import Blueprint, response

from ..common_auth import login_user, check_admin


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
