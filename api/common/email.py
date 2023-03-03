# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - email functions
"""
import secrets
import logging
from collections import namedtuple

import aiohttp
from quart import current_app as app

from ..errors import BadInput

log = logging.getLogger(__name__)
Error = namedtuple("Error", "status")


async def gen_email_token(user_id, table: str, count: int = 0) -> str:
    """Generate a token for email usage.

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
    if count == 11:
        # it really shouldn't happen,
        # but we better be ready for it.
        raise BadInput("Failed to generate an email hash.")

    possible = secrets.token_hex(32)

    # check if hash already exists
    other_id = await app.db.fetchval(
        f"""
    SELECT user_id
    FROM {table}
    WHERE hash = $1 AND now() < expiral
    """,
        possible,
    )

    if other_id:
        # retry with count + 1
        await gen_email_token(user_id, table, count + 1)

    hashes = await app.db.fetchval(
        f"""
    SELECT COUNT(*)
    FROM {table}
    WHERE user_id = $1 AND now() < expiral
    """,
        user_id,
    )

    if hashes > 3:
        raise BadInput(
            "You already generated more than 3 tokens " "in the time period."
        )

    return possible


async def send_email(user_email: str, subject: str, email_body: str) -> tuple:
    """Send an email to a user using the Mailgun API."""
    econfig = app.cfg
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

    if not user_email:
        return (Error(6969), None), None

    resp = await send_email(user_email, subject, body)

    log.info(f"Sent {len(body)} bytes email to {user_id} " f"{user_email} {subject!r}")

    return resp, user_email


def fmt_email(string, **kwargs):
    """Format an email"""
    base = {
        "inst_name": app.cfg.INSTANCE_NAME,
        "support": app.cfg.SUPPORT_EMAIL,
        "main_url": app.cfg.MAIN_URL,
        "main_invite": app.cfg.MAIN_INVITE,
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
    token = await gen_email_token(user_id, "email_activation_tokens")

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
