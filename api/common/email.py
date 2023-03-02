# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - email functions
"""
import secrets
import logging
from collections import namedtuple
from enum import Enum, auto

import aiohttp
from quart import current_app as app

from ..errors import BadInput

log = logging.getLogger(__name__)
Error = namedtuple("Error", "status")


class EmailTokenType(Enum):
    password_reset = auto()
    account_deletion = auto()
    account_activation = auto()
    datadump_result = auto()

    def to_table_name(self) -> str:
        return {
            self.__class__.password_reset: "email_pwd_reset_tokens",
            self.__class__.account_deletion: "email_deletion_tokens",
            self.__class__.account_activation: "email_activation_tokens",
            self.__class__.datadump_result: "email_dump_tokens",
        }[self]


async def make_email_token(user_id, token_type: EmailTokenType, count: int = 0) -> str:
    """Generate a token for email usage and inserts it on the relevant database.

    Calls the database to give an unique token.

    Parameters
    ----------
    app: sanic.App
        Application instance for database access.
    user_id: int
        User snowflake ID.
    table: str
        The table to be used for checking.

    Returns
    -------
    str
        The email token to be used.

    Raises
    ------
    BadInput
        When the funcion entered more than 10 retries,
        or there are more than 3 tokens issued in the span
        of a time window (defined by the table)
    """

    table_name = token_type.to_table_name()

    if count == 11:
        # it really shouldn't happen,
        # but we better be ready for it.
        raise BadInput("Failed to generate an email hash.")

    possible_token = secrets.token_hex(32)

    # check if hash already exists
    other_id = await app.db.fetchval(
        f"""
    SELECT user_id
    FROM {table_name}
    WHERE hash = $1 AND now() < expiral
    """,
        possible_token,
    )

    if other_id:
        # retry with count + 1
        return await make_email_token(user_id, token_type, count=count + 1)

    hashes = await app.db.fetchval(
        f"""
    SELECT COUNT(*)
    FROM {table_name}
    WHERE user_id = $1 AND now() < expiral
    """,
        user_id,
    )

    if hashes > 3:
        raise BadInput("You already generated more than 3 tokens in the time period.")

    log.info("generated email token %r for type %r", possible_token, token_type)

    await app.db.execute(
        f"""
    INSERT INTO {table_name} (hash, user_id)
    VALUES ($1, $2)
    """,
        possible_token,
        user_id,
    )

    return possible_token


# TODO this is a weird interface. errors are not bubbled up as exceptions
# to the callers, requiring them to do if checks and fail if they want to.
#
# this also does not handle actual failure. we should retry on email failure
#
# this also ties us to mailgun's HTTP API. this should be SMTP
#
# all of these would be more nicely handled with a dedicated email job queue.
async def send_email(user_email: str, subject: str, email_body: str) -> tuple:
    """Send an email to a user using the Mailgun API.

    Prefer using the send_user_email interface instead of this one.
    """
    econfig = app.econfig
    mailgun_url = f"https://api.mailgun.net/v3/{econfig.MAILGUN_DOMAIN}" "/messages"

    _inst_name = econfig.INSTANCE_NAME

    auth = aiohttp.BasicAuth("api", econfig.MAILGUN_API_KEY)
    data = {
        "from": f"{_inst_name} <automated@{econfig.MAILGUN_DOMAIN}>",
        "to": [user_email],
        # make sure everything passes through fmt_email
        # before sending
        "subject": fmt_email(subject),
        "text": fmt_email(email_body),
    }

    async with app.session.post(mailgun_url, auth=auth, data=data) as resp:
        return resp, await resp.text()


async def send_user_email(user_id: int, subject: str, body: str) -> tuple:
    """Send an email to a user, given user ID."""
    user_email = await app.db.fetchval(
        """
    SELECT email
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )
    if user_email is None:
        raise AssertionError("User ID not found")

    bundled_response = await send_email(user_email, subject, body)
    resp, _body = bundled_response

    if resp.status != 200:
        log.error("failed to send email to %r %r, got %r", user_id, user_email, resp)
        raise Exception("Failed to send email.")

    log.info("sent %d bytes email to %d %r %r", len(body), user_id, user_email, subject)
    return bundled_response, user_email


def fmt_email(string, **kwargs):
    """Format an email"""
    base = {
        "inst_name": app.econfig.INSTANCE_NAME,
        "support": app.econfig.SUPPORT_EMAIL,
        "main_url": app.econfig.MAIN_URL,
        "main_invite": app.econfig.MAIN_INVITE,
    }

    base.update(kwargs)
    log.debug("formatting %r", string)
    return string.replace("{}", "{{}}").format(**base)


async def uid_from_email(token: str, table: str, raise_err: bool = True) -> int:
    """Get user ID from email."""
    user_id = await app.db.fetchval(
        f"""
    SELECT user_id
    FROM {table}
    WHERE hash=$1
    """,
        token,
    )

    if not user_id and raise_err:
        raise BadInput("No user found with the token")

    return user_id


async def get_owner(domain_id: int) -> int:
    return await app.db.fetchval(
        """
    SELECT user_id
    FROM domain_owners
    WHERE domain_id = $1
    """,
        domain_id,
    )


async def clean_etoken(token: str, table: str) -> bool:
    res = await app.db.execute(
        f"""
    DELETE FROM {table}
    WHERE hash=$1
    """,
        token,
    )

    return res == "DELETE 1"


async def activate_email_send(user_id: int):
    token = await make_email_token(user_id, EmailTokenType.account_activation)

    await app.db.execute(
        """
    INSERT INTO email_activation_tokens (hash, user_id)
    VALUES ($1, $2)
    """,
        token,
        user_id,
    )

    token_url = fmt_email("{main_url}/api/activate_email?key={key}", key=token)

    body = fmt_email(
        """
This is an automated email from {inst_name}
about your account activation.

An administrator confirmed your account for proper activation
and you can activate your account at {token_url}

You only need to use this URL once. Other attempts at using
the URL will give you an error.

Welcome to {inst_name}!

Send an email to {support} if any questions arise.
Do not reply to this automated email.

 - {inst_name}, {main_url}
""",
        token_url=token_url,
    )

    subject = fmt_email("{inst_name} - account activation")
    return await send_user_email(user_id, subject, body)
