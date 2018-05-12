"""
Common authentication-related functions.
"""
import bcrypt
import itsdangerous
import logging

from .common import SIGNERS, TokenType, check_bans
from .errors import BadInput, FailedAuth, NotFound

log = logging.getLogger(__name__)


async def pwd_hash(request, password: str) -> str:
    """Generate a hash for any given password"""
    password_bytes = bytes(password, 'utf-8')
    hashed = request.app.loop.run_in_executor(None,
                                              bcrypt.hashpw,
                                              password_bytes,
                                              bcrypt.gensalt(14)
                                              )

    return (await hashed).decode('utf-8')


async def pwd_check(request, stored: str, password: str):
    """Raw version of password_check."""
    pwd_bytes = bytes(password, 'utf-8')
    pwd_orig = bytes(stored, 'utf-8')

    future = request.app.loop.run_in_executor(None,
                                              bcrypt.checkpw,
                                              pwd_bytes, pwd_orig)

    if not await future:
        raise FailedAuth('user or password invalid')


async def password_check(request, user_id: int, password: str):
    """Query password hash from user_id and compare with given."""
    stored = await request.app.db.fetchval("""
        select password_hash
        from users
        where user_id = $1
    """, user_id)

    await pwd_check(request, stored, password)


async def check_admin(request, user_id: int, error_on_nonadmin: bool = True):
    """Checks if the given user is an admin

    Returns True if user is an admin, False if not.
    Should return None if user is not found. I think.

    If error_on_nonadmin is set to True, then a FailedAuth exception will be
    raised if the user is not an admin.
    """
    is_admin = await request.app.db.fetchval("""
        select admin
        from users
        where user_id = $1
    """, user_id)

    if error_on_nonadmin and not is_admin:
        raise FailedAuth('User is not an admin.')

    return is_admin


async def check_domain(request, domain_name: str, error_on_nodomain=True):
    """Checks if a domain exists, by domain

    returns its record it if does, returns None if it doesn't"""

    # This is hacky but it works so you can't really blame me
    # Unless you send a fix first, then you can blame me :)
    subd_wildcard_name = domain_name.replace(domain_name.split(".")[0], "*")
    domain_wildcard_name = "*." + domain_name

    domain_info = await request.app.db.fetchrow("""
        SELECT *
        FROM domains
        WHERE domain = $1
        OR domain = $2
        OR domain = $3
    """, domain_name, subd_wildcard_name, domain_wildcard_name)

    if error_on_nodomain and not domain_info:
        raise NotFound('This domain does not exist in this elixire instance.')

    return domain_info


# TODO: reduce code repetition
async def check_domain_id(request, domain_id: int, error_on_nodomain=True):
    """Checks if a domain exists, by id

    returns its record it if does, returns None if it doesn't"""
    domain_info = await request.app.db.fetchrow("""
        SELECT *
        FROM domains
        WHERE domain_id = $1
    """, domain_id)

    if error_on_nodomain and not domain_info:
        raise NotFound('This domain does not exist in this elixire instance.')

    return domain_info


async def login_user(request):
    """
    Login one user, given its username and password.

    Returns a partial user row.
    """
    try:
        username = request.json['user']
        password = request.json['password']
    except (TypeError, KeyError):
        raise BadInput('Bad payload for user/password auth')

    user = await request.app.storage.actx_username(username)

    if not user:
        log.info(f'user {username!r} does not exist')
        raise FailedAuth('user or password invalid')

    if not user['active']:
        log.info(f'user {username!r} is not active')
        raise FailedAuth('user or password invalid')

    await check_bans(request, user['user_id'])
    await pwd_check(request, user['password_hash'], password)

    return user


async def token_check(request, wanted_type=None) -> int:
    """
    Check if a token is valid.
    By default does not care about the token type.
    """
    try:
        token = request.headers['Authorization']
    except (TypeError, KeyError):
        raise BadInput('no token provided')

    token_type = token.count('.')
    if wanted_type and wanted_type != token_type:
        raise FailedAuth('invalid token type')

    data = token.split('.')
    try:
        user_id = int(data[0])
    except (TypeError, ValueError):
        raise FailedAuth('invalid token format')

    user = await request.app.storage.actx_userid(user_id)

    if not user:
        raise FailedAuth('unknown user ID')

    print(user)
    if not user['active']:
        raise FailedAuth('inactive user')

    await check_bans(request, user_id)

    pwdhash = user['password_hash']

    signer = SIGNERS[token_type](pwdhash)
    token = token.encode('utf-8')
    try:
        if token_type == TokenType.NONTIMED:
            signer.unsign(token)
        elif token_type == TokenType.TIMED:
            signer.unsign(token,
                          max_age=request.app.econfig.TIMED_TOKEN_AGE)
        else:
            raise FailedAuth('invalid token type')
    except (itsdangerous.SignatureExpired, itsdangerous.BadSignature):
        raise FailedAuth('invalid or expired token')

    return user_id


def gen_token(user, token_type=TokenType.TIMED) -> str:
    """Generate one token."""
    signer = SIGNERS[token_type](user['password_hash'])
    uid = bytes(str(user['user_id']), 'utf-8')
    return signer.sign(uid)
