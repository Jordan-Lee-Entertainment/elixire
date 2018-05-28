import logging

from sanic import Blueprint
from sanic import response

from ..errors import FailedAuth, FeatureDisabled, BadInput
from ..common_auth import token_check, password_check, pwd_hash,\
    check_admin, check_domain_id
from ..common import gen_email_token, send_email
from ..schema import validate, PROFILE_SCHEMA, DEACTIVATE_USER_SCHEMA, PASSWORD_RESET_SCHEMA, PASSWORD_RESET_CONFIRM_SCHEMA

bp = Blueprint('profile')
log = logging.getLogger(__name__)


async def _update_password(request, user_id, new_pwd):
    new_hash = await pwd_hash(request, new_pwd)

    await request.app.db.execute("""
        UPDATE users
        SET password_hash = $1
        WHERE user_id = $2
    """, new_hash, user_id)

    await request.app.storage.invalidate(user_id, 'password_hash')


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
    SELECT user_id, username, active, email, consented, admin, subdomain, domain, paranoid
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
    new_paranoid = payload.get('paranoid')

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

    if new_paranoid is not None:
        await request.app.db.execute("""
            UPDATE users
            SET paranoid = $1
            WHERE user_id = $2
        """, new_paranoid, user_id)

        updated.append('paranoid')

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
        await _update_password(request, user_id, new_pwd)
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

@bp.delete('/api/account')
async def deactive_own_user(request):
    """Deactivate the current user.

    This does not delete right away for reasons.

    Sends an email to them asking for actual confirmation.
    """
    user_id = await token_check(request)
    payload = validate(request.json, DEACTIVATE_USER_SCHEMA)
    await password_check(request, user_id, payload['password'])

    user_email = await request.app.db.fetchval("""
    SELECT email
    FROM users
    WHERE user_id = $1
    """, user_id)

    if not user_email:
        raise BadInput('No email was found.')

    _inst_name = request.app.econfig.INSTANCE_NAME
    _support = request.app.econfig.SUPPORT_EMAIL

    email_token = await gen_email_token(request.app, user_id, 'email_deletion_tokens')

    log.info(f'Generated email hash {email_token} for account deactivation')

    await request.app.db.execute("""
    INSERT INTO email_deletion_tokens(hash, user_id)
    VALUES ($1, $2)
    """, email_token, user_id)

    email_body = f"""This is an automated email from {_inst_name}
about your account deletion.

Please visit {request.app.econfig.MAIN_URL}/deleteconfirm.html#{email_token} to
confirm the deletion of your account.

The link will be invalid in 12 hours. Do not share it with anyone.

Reply to {_support} if you have any questions.

If you did not make this request, email {_support} since your account
might be compromised.

Do not reply to this email specifically, it will not work.

- {_inst_name}, {request.app.econfig.MAIN_URL}
"""

    resp = await send_email(request.app, user_email,
                            f'{_inst_name} - account deactivation request', email_body)

    return response.json({
        'success': resp.status == 200
    })


@bp.post('/api/delete_confirm')
async def deactivate_user_from_email(request):
    """Actually deactivate the account."""
    try:
        cli_hash = str(request.args['token'][0])
    except (KeyError, TypeError, ValueError):
        raise BadInput('No valid token provided.')

    user_id = await request.app.db.fetchval("""
    SELECT user_id
    FROM email_deletion_tokens
    WHERE hash=$1 AND now() < expiral
    """, cli_hash)

    if not user_id:
        raise BadInput('No user found with that email token.')

    await request.app.db.execute("""
    UPDATE users
    SET active = false
    WHERE user_id = $1
    """, user_id)

    await request.app.db.execute("""
    DELETE FROM email_deletion_tokens
    WHERE hash=$1
    """, cli_hash)

    log.warning(f'Deactivated user ID {user_id} by request.')

    return response.json({
        'success': True
    })

@bp.post('/api/reset_password')
async def reset_password_req(request):
    """Send a password reset request."""
    payload = validate(request.json, PASSWORD_RESET_SCHEMA)
    username = payload['username']

    udata = await request.app.db.fetchrow("""
    SELECT email, user_id
    FROM users
    WHERE username = $1
    """, username)

    if not udata:
        raise BadInput('User not found')

    user_email = udata['email']
    user_id = udata['user_id']

    _inst_name = request.app.econfig.INSTANCE_NAME
    _support = request.app.econfig.SUPPORT_EMAIL

    email_token = await gen_email_token(request.app, user_id, 'email_pwd_reset_tokens')

    await request.app.db.execute("""
    INSERT INTO email_pwd_reset_tokens (hash, user_id)
    VALUES ($1, $2)
    """, email_token, user_id)

    email_body = f"""This is an automated email from {_inst_name}
about your password reset.

Please visit {request.app.econfig.MAIN_URL}/password_reset.html#{email_token} to
reset your password.

The link will be invalid in 30 minutes. Do not share the link with anyone else.
Nobody from support will ask you for this link.

Reply to {_support} if you have any questions.

Do not reply to this email specifically, it will not work.

- {_inst_name}, {request.app.econfig.MAIN_URL}
"""

    resp = await send_email(request.app, user_email,
                            f'{_inst_name} - password reset request', email_body)

    return response.json({
        'success': resp.status == 200
    })


@bp.post('/api/reset_password_confirm')
async def password_reset_confirmation(request):
    """Handle the confirmation of a password reset."""
    payload = validate(request.json, PASSWORD_RESET_CONFIRM_SCHEMA)
    token = payload['token']
    new_pwd = payload['new_password']

    user_id = await request.app.db.fetchval("""
    SELECT user_id
    FROM email_pwd_reset_tokens
    WHERE hash = $1 AND now() < expiral
    """, token)

    if not user_id:
        raise BadInput('Invalid token.')

    # reset password
    await _update_password(request, user_id, new_pwd)

    await request.app.db.execute("""
    DELETE FROM email_pwd_reset_tokens
    WHERE hash = $1
    """, token)

    return response.json({
        'success': True
    })
