from sanic import Blueprint
from sanic import response

from ..errors import FailedAuth
from ..common_auth import token_check, password_check, pwd_hash, check_admin
from ..schema import validate, PROFILE_SCHEMA

bp = Blueprint('profile')


@bp.get('/api/domains')
async def domainlist_handler(request):
    """Gets the domain list."""
    user_id = await token_check(request)

    is_admin = await check_admin(request, user_id, False)
    adm_string = "" if is_admin else "WHERE admin_only = False"
    domain_records = await request.app.db.fetch("""
    SELECT domain
    FROM domains
    """ + adm_string)

    domains = [record["domain"] for record in domain_records]
    return response.json({"domains": domains})


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

    limits = await request.app.db.fetchrow("""
    SELECT blimit, shlimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    bytes_used = await request.app.db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    AND file_id > time_snowflake(now() - interval '7 days')
    """, user_id)

    shortens_used = await request.app.db.fetch("""
    SELECT shorten_id
    FROM shortens
    WHERE uploader = $1
    AND shorten_id > time_snowflake(now() - interval '7 days')
    """, user_id)

    return response.json({
        'limit': limits["blimit"],
        'used': bytes_used,
        'shortenlimit': limits["shlimit"],
        'shortenused': len(shortens_used)
    })
