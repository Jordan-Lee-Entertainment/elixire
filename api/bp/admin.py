"""
elixire - admin routes
"""

from sanic import Blueprint, response

from ..common_auth import token_check, check_admin
from ..errors import NotFound, BadInput


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

    try:
        page = int(request.json['page'])
    except (TypeError, ValueError):
        raise BadInput('Invalid page integer.')

    # hmmm maybe more users per page?
    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain
    FROM users
    LIMIT 15
    OFFSET ($1 * 15)
    """, page)

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

@bp.post('/api/admin/activate/<user_id>')
async def activate_user(request, user_id: int):
    """Activate one user, given its ID."""
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    result = await request.app.db.execute("""
    UPDATE users
    SET active = false
    WHERE user_id = $1
    """, user_id)

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    return response.json({
        'success': True
    })

@bp.post('/api/admin/deactivate/<user_id>')
async def deactivate_user(request, user_id: int):
    """Deactivate one user, given its ID."""
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    result = await request.app.db.execute("""
    UPDATE users
    SET active = false
    WHERE user_id = $1
    """, user_id)

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    return response.json({
        'success': True
    })
