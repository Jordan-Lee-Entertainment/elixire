# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import secrets
import logging
from collections import namedtuple
from smtplib import SMTP, SMTP_SSL
from email.message import EmailMessage
from typing import Tuple

from quart import current_app

import aiohttp

from ..errors import BadInput

log = logging.getLogger(__name__)


async def gen_email_token(user_id, table: str, _count: int = 0) -> str:
    """Generate a token for email usage.

    Calls the database to give an unique token.

    Parameters
    ----------
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
    if _count == 11:
        # it really shouldn't happen,
        # but we better be ready for it.
        raise BadInput("Failed to generate an email hash.")

    possible = secrets.token_hex(32)

    # check if hash already exists
    other_id = await current_app.db.fetchval(
        f"""
        SELECT user_id
        FROM {table}
        WHERE hash = $1 AND now() < expiral
        """,
        possible,
    )

    if other_id:
        # retry with count + 1
        await gen_email_token(user_id, table, _count + 1)

    hashes = await current_app.db.fetchval(
        f"""
        SELECT COUNT(*)
        FROM {table}
        WHERE user_id = $1 AND now() < expiral
        """,
        user_id,
    )

    if hashes > 3:
        raise BadInput(
            "You already generated more than 3 tokens in the expiral time period."
        )

    return possible


def raw_send_email(cfg: dict, to: str, subject: str, content: str):
    """Send an email via SMTP."""

    msg = EmailMessage()
    msg.set_content(content)

    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to

    log.debug("smtp send %r %r", cfg["host"], cfg["port"])

    smtp_class = SMTP_SSL if cfg["tls_mode"] == "tls" else SMTP

    with smtp_class(host=cfg["host"], port=cfg["port"]) as smtp:
        if cfg["tls_mode"] == "starttls":
            log.debug("smtp starttls")
            smtp.starttls()

        log.debug("smtp login")
        smtp.login(cfg["username"], cfg["password"])

        log.debug("smtp send message")
        smtp.send_message(msg)

    log.debug("smtp done")


async def send_email(user_email: str, subject: str, content: str) -> bool:
    try:
        await current_app.loop.run_in_executor(
            None,
            raw_send_email,
            current_app.econfig.SMTP_CONFIG,
            user_email,
            fmt_email(current_app, subject),
            fmt_email(current_app, content),
        )
        return True
    except Exception:
        log.exception("Failed to send email")
        # TODO raise own exception instead
        return False


async def send_email_to_user(user_id: int, subject: str, body: str) -> Tuple[bool, str]:
    """Send an email to a user, given user ID.

    Returns the success status of the email and the actual user email.
    """
    user_email = await current_app.db.fetchval(
        """
        SELECT email
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    email_ok = await send_email(user_email, subject, body)
    log.info("sent %d bytes email to %d %r %r", len(body), user_id, user_email, subject)

    return email_ok, user_email


def fmt_email(app, string, **kwargs):
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


async def uid_from_email_token(token: str, table: str, raise_err: bool = True) -> int:
    """Get user ID from a random email token."""
    user_id = await current_app.db.fetchval(
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


async def get_owner(app, domain_id: int) -> int:
    return await app.db.fetchval(
        """
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """,
        domain_id,
    )


async def clean_etoken(token: str, table: str) -> bool:
    """Delete the given token from the given table."""
    res = await current_app.db.execute(
        f"""
        DELETE FROM {table}
        WHERE hash=$1
        """,
        token,
    )

    return res == "DELETE 1"


async def activate_email_send(app, user_id: int):
    token = await gen_email_token(app, user_id, "email_activation_tokens")

    await app.db.execute(
        """
        INSERT INTO email_activation_tokens (hash, user_id)
        VALUES ($1, $2)
        """,
        token,
        user_id,
    )

    token_url = fmt_email(app, "{main_url}/api/activate_email?key={key}", key=token)

    body = fmt_email(
        app,
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

    subject = fmt_email(app, "{inst_name} - account activation")
    return await send_user_email(app, user_id, subject, body)
