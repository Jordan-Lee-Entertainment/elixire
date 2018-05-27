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


@bp.get('/api/admin/listusers/<page:int>')
async def list_users_handler(request, page: int):
    """List users in the service"""
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain, subdomain
    FROM users
    LIMIT 20
    OFFSET ($1 * 20)
    """, page)

    def _cnv(row):
        drow = dict(row)
        drow['user_id'] = str(row['user_id'])
        return drow

    return response.json(list(map(_cnv, data)))


@bp.get('/api/admin/list_inactive/<page:int>')
async def inactive_users_handler(request, page: int):
    user_id = await token_check(request)
    await check_admin(request, user_id, True)

    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain, subdomain
    FROM users
    WHERE active=false
    LIMIT 20
    OFFSET ($1 * 20)
    """, page)

    def _cnv(row):
        drow = dict(row)
        drow['user_id'] = str(row['user_id'])
        return drow

    return response.json(list(map(_cnv, data)))


@bp.get('/api/admin/users/<user_id:int>')
async def get_user_handler(request, user_id: int):
    """Get a user's details in the service."""
    requester_id = await token_check(request)
    await check_admin(request, requester_id, True)

    udata = await request.app.db.fetchrow("""
    SELECT user_id, username, active, admin, domain, subdomain
    FROM users
    WHERE user_id=$1
    """, user_id)

    if not udata:
        raise NotFound('User not found')

    dudata = dict(udata)
    dudata['user_id'] = str(dudata['user_id'])

    return response.json(dudata)


@bp.post('/api/admin/activate/<user_id:int>')
async def activate_user(request, user_id: int):
    """Activate one user, given its ID."""
    caller_id = await token_check(request)
    await check_admin(request, caller_id, True)

    result = await request.app.db.execute("""
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    return response.json({
        'success': True,
        'result': result,
    })


@bp.post('/api/admin/deactivate/<user_id:int>')
async def deactivate_user(request, user_id: int):
    """Deactivate one user, given its ID."""
    caller_id = await token_check(request)
    await check_admin(request, caller_id, True)

    result = await request.app.db.execute("""
    UPDATE users
    SET active = false
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')

    if result == "UPDATE 0":
        raise BadInput('Provided user ID does not reference any user.')

    return response.json({
        'success': True,
        'result': result
    })
