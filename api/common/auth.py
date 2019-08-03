# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - common auth
    Common authentication-related functions.
"""
import logging
from typing import Tuple, Union

import bcrypt
import itsdangerous

from quart import request, current_app as app

from api.errors import FailedAuth, NotFound
from api.schema import validate, LOGIN_SCHEMA
from .common import TokenType, check_bans, gen_filename

log = logging.getLogger(__name__)


async def gen_shortname(user_id: int, table: str = "files") -> Tuple[str, int]:
    """Generate a shortname for a file.

    Checks if the user is in paranoid mode.
    """
    is_paranoid = await check_paranoid(user_id)

    # TODO config
    shortname_len = 8 if is_paranoid else app.econfig.SHORTNAME_LEN
    return await gen_filename(shortname_len, table)


def get_token() -> str:
    """Get a token from the request.

    Fetches a token from the url arguments,
    if it fails, will fetch from the Authorization header.
    """
    try:
        return request.args["token"]
    except KeyError:
        return request.headers["Authorization"]


async def pwd_hash(password: str) -> str:
    """Generate a hash for any given password"""
    password_bytes = bytes(password, "utf-8")
    hashed = app.loop.run_in_executor(
        None, bcrypt.hashpw, password_bytes, bcrypt.gensalt(14)
    )

    return (await hashed).decode("utf-8")


async def pwd_check(stored: str, password: str):
    """Raw version of password_check."""
    pwd_bytes = password.encode("utf-8")
    pwd_orig = stored.encode("utf-8")

    future = app.loop.run_in_executor(None, bcrypt.checkpw, pwd_bytes, pwd_orig)

    if not await future:
        raise FailedAuth("User or password invalid")


async def password_check(user_id: int, password: str):
    """Query password hash from user_id and compare with given.

    Raises FailedAuth on invalid password.
    """
    stored = await app.db.fetchval(
        """
        select password_hash
        from users
        where user_id = $1
    """,
        user_id,
    )

    await pwd_check(stored, password)


async def check_admin(user_id: int, error_on_nonadmin: bool = True) -> bool:
    """Checks if the given user is an admin.

    Returns
    -------
    bool
        Representing if the user is an admin or not.
    None
        When user doesn't exist.

    Raises
    ------
    FailedAuth
        When user is not an admin and error_on_nonadmin is set to True.
    """
    is_admin = await app.db.fetchval(
        """
        select admin
        from users
        where user_id = $1
    """,
        user_id,
    )

    if error_on_nonadmin and not is_admin:
        raise FailedAuth("User is not an admin.")

    return is_admin


async def check_paranoid(user_id: int) -> bool:
    """If the user is in paranoid mode.

    Returns None if user does not exist.
    """
    is_paranoid = await app.db.fetchval(
        """
        select paranoid
        from users
        where user_id = $1
    """,
        user_id,
    )

    return is_paranoid


async def check_domain(domain_name: str, error_on_nodomain=True) -> dict:
    """Checks if a domain exists, by domain

    returns its record it if does, returns None if it doesn't"""

    # This is hacky but it works so you can't really blame me
    # Unless you send a fix first, then you can blame me :)
    subd_wildcard_name = domain_name.replace(domain_name.split(".")[0], "*")
    domain_wildcard_name = "*." + domain_name

    domain_info = await app.db.fetchrow(
        """
        SELECT *
        FROM domains
        WHERE domain = $1
        OR domain = $2
        OR domain = $3
    """,
        domain_name,
        subd_wildcard_name,
        domain_wildcard_name,
    )

    if error_on_nodomain and not domain_info:
        raise NotFound("This domain does not exist in this elixire instance.")

    return domain_info


# TODO: reduce code repetition
async def check_domain_id(domain_id: int, error_on_nodomain=True):
    """Checks if a domain exists, by id

    returns its record it if does, returns None if it doesn't"""
    domain_info = await app.db.fetchrow(
        """
        SELECT *
        FROM domains
        WHERE domain_id = $1
    """,
        domain_id,
    )

    if error_on_nodomain and not domain_info:
        raise NotFound("This domain does not exist in this elixire instance.")

    return domain_info


async def login_user() -> dict:
    """Log in a user, given their username and password.

    Returns a partial user dictionary.
    """
    payload = validate(await request.get_json(), LOGIN_SCHEMA)
    username, password = payload["user"], payload["password"]

    partial_user = await app.storage.auth_user_from_username(username)

    if partial_user is None:
        log.info(f"login: {username!r} does not exist")
        raise FailedAuth("User or password invalid")

    await pwd_check(partial_user["password_hash"], password)

    if not partial_user["active"]:
        log.warning(f"login: {username!r} is not active")
        raise FailedAuth("User is deactivated")

    await check_bans(partial_user["user_id"])
    return partial_user


def _try_int(value: str) -> int:
    """Try converting a given string to an int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise FailedAuth("invalid token format")


def _try_unsign(signer, token: Union[str, bytes], token_age: int = None):
    """Try to unsign a token given the signer,
    token, and token_age if possible.

    This will convert the specific itsdangerous
    exception in regards to tokens into our FailedAuth
    exception.
    """
    try:
        if token_age is not None:
            signer.unsign(token, max_age=token_age)
        else:
            signer.unsign(token)
    except (itsdangerous.SignatureExpired, itsdangerous.BadSignature):
        raise FailedAuth("invalid or expired token")


async def token_check() -> int:
    """Check if a token is valid. Returns user ID upon success.

    This will check if the token given in the request is an API token or not,
    performing proper validation depending on its type.
    """
    # TODO config
    cfg = app.econfig

    try:
        token = get_token()

        # make sure we get something that isn't empty
        assert token
    except (TypeError, KeyError, AssertionError):
        raise FailedAuth("no token provided")

    # decrease calls to storage in half by checking context beforehand
    # (request.ctx is set by the ratelimiter on api/bp/ratelimit.py)
    try:
        _, uid = request.ctx
        return uid
    except AttributeError:
        pass

    data = token.split(".")
    dotcount = token.count(".")

    block_1 = data[0]
    is_apitoken = block_1[0] == "u"

    if is_apitoken:
        # take out the 'u' prefix
        # and extract the id
        user_id = _try_int(block_1[1:])
    else:
        user_id = _try_int(block_1)

    partial_user = await app.storage.auth_user_from_user_id(user_id)

    if not partial_user:
        raise FailedAuth("unknown user ID")

    if not partial_user["active"]:
        raise FailedAuth("inactive user")

    await check_bans(user_id)

    salt = partial_user["password_hash"]

    if not cfg.TOKEN_SECRET:
        raise FailedAuth(
            "TOKEN_SECRET is not set. Please contact " "the instance administrator."
        )

    key = cfg.TOKEN_SECRET

    # now comes the tricky part, since we need to keep
    # at least some level of backwards compatibility with the
    # old token format (at least for some time).

    if dotcount == TokenType.NONTIMED:
        # NOTE: when removing old-format tokens,
        # replace this unsigning with a
        # FailedAuth exception

        # salt here is password_hash, which is the key
        # for every old non-timed token.
        signer = itsdangerous.Signer(salt)

        # itsdangerous.Signer does not like
        # strings, only bytes.
        token_bytes = token.encode("utf-8")
        _try_unsign(signer, token_bytes)
        return user_id

    # at this point in code the token is:
    #  - a new-format uploader token
    #  - a timed token (not uploader)
    # and we know if it is or not via is_apitoken

    # one thing we know is that both tokens are timed, so
    # we create TimestampSigner instead of Signer, always.

    signer = itsdangerous.TimestampSigner(key, salt=salt)

    # api tokens don't have checks in regards to their age.
    token_age = None if is_apitoken else cfg.TIMED_TOKEN_AGE

    _try_unsign(signer, token, token_age)
    return user_id


def gen_token(user: dict, token_type=TokenType.TIMED) -> str:
    """Generate one token."""
    # TODO config
    cfg = app.econfig

    salt = user["password_hash"]

    if not cfg.TOKEN_SECRET:
        raise FailedAuth(
            "TOKEN_SECRET is not set. Please contact " "the instance administrator."
        )

    key = cfg.TOKEN_SECRET

    signer = itsdangerous.TimestampSigner(key, salt=salt)
    uid = str(user["user_id"])

    if token_type == TokenType.NONTIMED:
        # prefix "u" to the token
        # so that we know that the token is to be
        # treated as an API token
        uid = f"u{uid}"

    return signer.sign(uid).decode("utf-8")
