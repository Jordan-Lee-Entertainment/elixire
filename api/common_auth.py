"""
Common authentication-related functions.
"""

import bcrypt
import itsdangerous

from .common import SIGNERS, TokenType
from .errors import BadInput, FailedAuth


async def login_user(request):
    """
    Login one user, given its username and password.

    Returns a partial user row.
    """
    try:
        username = request.json['user']
        password = request.json['password']
    except (TypeError, KeyError):
        raise BadInput('bad input')

    user = await request.app.db.fetchrow("""
    SELECT user_id, active, password_hash
    FROM users
    WHERE username = $1
    """, username)

    if not user:
        raise FailedAuth('user or password invalid')

    if not user['active']:
        raise FailedAuth('user or password invalid')

    # check password validity
    pb = bytes(password, 'utf-8')
    ph = bytes(user['password_hash'], 'utf-8')
    future = request.app.loop.run_in_executor(None,
                                              bcrypt.checkpw,
                                              pb, ph)

    if not await future:
        raise FailedAuth('user or password invalid')

    return user


async def token_check(request, wanted_type=None):
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

    user = await request.app.db.fetchrow("""
    SELECT password_hash, active
    FROM users
    WHERE user_id = $1
    """, user_id)

    if not user:
        raise FailedAuth('unknown user ID')

    if not user['active']:
        raise FailedAuth('inactive user')

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


def gen_token(user, token_type=TokenType.TIMED):
    signer = SIGNERS[token_type](user['password_hash'])
    uid = bytes(str(user['user_id']), 'utf-8')
    return signer.sign(uid)

