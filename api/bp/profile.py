from sanic import Blueprint
from sanic import response

from ..errors import FailedAuth
from ..common_auth import token_check, password_check, pwd_hash
from ..schema import validate, PROFILE_SCHEMA

bp = Blueprint('profile')


@bp.get('/api/profile')
async def profile_handler(request):
    """Get your basic information as a user."""

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


@bp.patch('/api/profile')
async def change_profile(request):
    """Change a user's profile."""
    user_id = await token_check(request)
    payload = validate(request.json, PROFILE_SCHEMA)

    updated = []

    password = payload.get('password')
    new_pwd = payload.get('new_password')

    if password:
        await password_check(request, user_id, password)
    else:
        raise FailedAuth('no password provided')

    if new_pwd and new_pwd != password:
        # we are already good from password_check call
        new_hash = await pwd_hash(request, new_pwd)

        await request.app.db.execute("""
            update users
            set password_hash = $1
            where user_id = $2
        """, new_hash, user_id)

        updated.append('password')

    return response.json({
        'updated_fields': updated,
    })


@bp.get('/api/limits')
async def limits_handler(request):
    """Query a user's limits."""
    user_id = await token_check(request)

    byte_limit = await request.app.db.fetchval("""
    SELECT blimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    used = await request.app.db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    AND file_id > time_snowflake(now() - interval '7 hours')
    """, user_id)

    return response.json({
        'limit': byte_limit,
        'used': used
    })
