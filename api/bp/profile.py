from sanic import Blueprint
from sanic import response

from ..common_auth import token_check

bp = Blueprint('profile')


@bp.route('/api/profile', methods=['OPTIONS', 'GET'])
async def profile_handler(request):
    """
    Get your basic information as a user.
    """
    # by default, token_check won't care which
    # token is it being fed with, it will only check.
    user_id = await token_check(request)
    user = await request.app.db.fetchrow("""
    SELECT *
    FROM users
    WHERE user_id = $1
    """, user_id)

    duser = dict(user)
    duser['user_id'] = str(duser['user_id'])
    duser.pop('password_hash')

    return response.json(duser)


@bp.route('/api/limits', methods=['OPTIONS', 'GET'])
async def limits_handler(request):
    user_id = await token_check(request)

    byte_limit = await request.app.db.fetchval("""
    SELECT blimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    return response.json({
        'limit': byte_limit,
    })

