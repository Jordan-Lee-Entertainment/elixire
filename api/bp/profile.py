from sanic import Blueprint
from sanic import response

from ..errors import FailedAuth, FeatureDisabled
from ..common_auth import token_check, password_check, pwd_hash,\
    check_admin, check_domain_id
from ..schema import validate, PROFILE_SCHEMA

bp = Blueprint('profile')


@bp.get('/api/domains')
async def domainlist_handler(request):
    """Gets the domain list."""

    # Only check if user's token is valid and their admin status
    # if they gave authorization.
    is_admin = False
    if 'Authorization' in request.headers:
        user_id = await token_check(request)
        is_admin = await check_admin(request, user_id, False)

    adm_string = "" if is_admin else "WHERE admin_only = false"
    domain_records = await request.app.db.fetch(f"""
    SELECT domain_id, domain
    FROM domains
    {adm_string}
    ORDER BY domain_id ASC
    """)

    adm_string_official = "" if is_admin else "AND admin_only = false"
    official_domains = await request.app.db.fetch(f"""
    SELECT domain_id
    FROM domains
    WHERE official = true {adm_string_official}
    ORDER BY domain_id ASC
    """)

    # dear god
    official_domains = [x[0] for x in official_domains]

    return response.json({"domains": dict(domain_records),
                          "officialdomains": official_domains})


@bp.get('/api/profile')
async def profile_handler(request):
    """Get your basic information as a user."""

    # by default, token_check won't care which
    # token is it being fed with, it will only check.
    user_id = await token_check(request)
    user = await request.app.db.fetchrow("""
    SELECT user_id, username, active, email, consented, admin, subdomain, domain
    FROM users
    WHERE user_id = $1
    """, user_id)

    limits = await get_limits(request.app.db, user_id)

    duser = dict(user)
    duser['user_id'] = str(duser['user_id'])
    duser['limits'] = limits

    return response.json(duser)


@bp.patch('/api/profile')
async def change_profile(request):
    """Change a user's profile."""
    if not request.app.econfig.PATCH_API_PROFILE_ENABLED:
        raise FeatureDisabled('changes on profile are currently disabled')

    user_id = await token_check(request)
    payload = validate(request.json, PROFILE_SCHEMA)

    updated = []

    password = payload.get('password')
    new_pwd = payload.get('new_password')
    new_domain = payload.get('domain')
    new_subdomain = payload.get('subdomain')
    new_email = payload.get('email')

    if password:
        await password_check(request, user_id, password)
    else:
        raise FailedAuth('no password provided')

    if new_domain is not None:
        # Check if domain exists
        domain_info = await check_domain_id(request, new_domain)

        # Check if user has perms for getting that domain
        is_admin = await check_admin(request, user_id, False)
        if domain_info["admin_only"] and not is_admin:
            raise FailedAuth("You're not an admin but you're "
                             "trying to switch to an admin-only domain.")

        await request.app.db.execute("""
            UPDATE users
            SET domain = $1
            WHERE user_id = $2
        """, new_domain, user_id)

        updated.append('domain')

    if new_subdomain is not None:
        await request.app.db.execute("""
            UPDATE users
            SET subdomain = $1
            WHERE user_id = $2
        """, new_subdomain, user_id)

        updated.append('subdomain')

    if new_email is not None:
        await request.app.db.execute("""
            UPDATE users
            SET email = $1
            WHERE user_id = $2
        """, new_email, user_id)

        updated.append('email')

    try:
        new_consent_state = payload['consented']

        await request.app.db.execute("""
            UPDATE users
            SET consented = $1
            WHERE user_id = $2
        """, new_consent_state, user_id)

        updated.append('consented')
    except KeyError:
        pass

    if new_pwd and new_pwd != password:
        # we are already good from password_check call
        new_hash = await pwd_hash(request, new_pwd)

        await request.app.db.execute("""
            UPDATE users
            SET password_hash = $1
            WHERE user_id = $2
        """, new_hash, user_id)

        await request.app.storage.invalidate(user_id, 'password_hash')

        updated.append('password')

    return response.json({
        'updated_fields': updated,
    })


async def get_limits(db, user_id):
    limits = await db.fetchrow("""
    SELECT blimit, shlimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    bytes_used = await db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    AND file_id > time_snowflake(now() - interval '7 days')
    """, user_id)

    shortens_used = await db.fetch("""
    SELECT shorten_id
    FROM shortens
    WHERE uploader = $1
    AND shorten_id > time_snowflake(now() - interval '7 days')
    """, user_id)

    return {
        'limit': limits["blimit"],
        'used': bytes_used,
        'shortenlimit': limits["shlimit"],
        'shortenused': len(shortens_used)
    }


@bp.get('/api/limits')
async def limits_handler(request):
    """Query a user's limits."""
    user_id = await token_check(request)

    limits = await get_limits(request.app.db, user_id)

    return response.json(limits)
