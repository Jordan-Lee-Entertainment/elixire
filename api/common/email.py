# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import secrets
import logging
import smtplib
from smtplib import SMTP, SMTP_SSL
from email.message import EmailMessage
from typing import Tuple

from quart import current_app as app

from ..errors import BadInput, EmailError

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
        await gen_email_token(user_id, table, _count + 1)

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


async def send_email(
    user_email: str, subject: str, content: str, *, _is_repeat: bool = False
) -> bool:
    if getattr(app, "_test", False):
        app._email_list.append(
            {"email": user_email, "subject": subject, "content": content}
        )

        return True

    try:
        await app.loop.run_in_executor(
            None,
            raw_send_email,
            app.econfig.SMTP_CONFIG,
            user_email,
            fmt_email(subject),
            fmt_email(content),
        )
    except smtplib.SMTPConnectError as exc:
        log.error("Failed to connect to server (%r), retry=%r", exc, not _is_repeat)
        if not _is_repeat:
            await asyncio.sleep(5)
            return await send_email(user_email, subject, content, _is_repeat=True)

        raise EmailError(f"Failed to connect to SMTP server: {exc!r}")
    except smtplib.SMTPException as exc:
        raise EmailError(f"smtp error: {exc!r}")
    except Exception as exc:
        log.exception("Failed to send email")
        raise EmailError(f"Failed to send email: {exc!r}")


async def send_email_to_user(
    user_id: int, subject: str, body: str, **kwargs
) -> Tuple[bool, str]:
    """Send an email to a user, given user ID.

    Returns the success status of the email and the actual user email.
    """
    user_email = await app.db.fetchval(
        """
        SELECT email
        FROM users
        WHERE user_id = $1
        """,
        user_id,
    )

    await send_email(user_email, subject, body, **kwargs)
    log.info("sent %d bytes email to %d %r %r", len(body), user_id, user_email, subject)
    return user_email


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


async def uid_from_email_token(token: str, table: str) -> int:
    """Get user ID from a random email token."""
    user_id = await app.db.fetchval(
        f"""
        SELECT user_id
        FROM {table}
        WHERE hash=$1
        """,
        token,
    )

    if user_id is None:
        raise BadInput("No user found with the token")

    return user_id


async def clean_etoken(token: str, table: str) -> bool:
    """Delete the given token from the given table."""
    res = await app.db.execute(
        f"""
        DELETE FROM {table}
        WHERE hash=$1
        """,
        token,
    )

    return res == "DELETE 1"


async def send_activation_email(user_id: int):
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

    return await send_email_to_user(user_id, "{inst_name} - account activation", body)


async def send_activated_email(user_id: int):
    if not app.econfig.NOTIFY_ACTIVATION_EMAILS:
        return

    email_body = """This is an automated email from {inst_name}
about your account request.

Your account has been activated and you can now log in
at {main_url}/login.html.

Welcome to {inst_name}!

Send an email to {support} if any questions arise.
Do not reply to this automated email.

- {inst_name}, {main_url}
"""

    return await send_email_to_user(
        user_id, "{inst_name} - Your account is now active", email_body
    )


async def send_register_email(email: str):
    """Send an email about the signup."""
    email_body = fmt_email(
        """This is an automated email from {inst_name}
about your signup.

It has been successfully dispatched to the system so that admins can
activate the account. You will not be able to login until the account
is activated.

Accounts that aren't on the discord server won't be activated.
{main_invite}

Please do not re-register the account. It will just decrease your chances
of actually getting an account activated.

Reply to {support} if you have any questions.
Do not reply to this email specifically, it will not work.

 - {inst_name}, {main_url}
"""
    )

    return await send_email(email, "{inst_name} - signup confirmation", email_body)


async def send_username_recovery_email(uname: str, email: str):
    email_body = fmt_email(
        """
This is an automated email from {inst_name} about
your username recovery.

Your username is {uname}.

 - {inst_name}, {main_url}
""",
        uname=uname,
    )

    return await send_email(email, "{inst_name} - username recovery", email_body)


async def send_deletion_confirm_email(user_id: int, email_token: str):
    email_body = fmt_email(
        """This is an automated email from {inst_name}
about your account deletion.

Please visit {main_url}/deleteconfirm.html#{email_token} to
confirm the deletion of your account.

The link will be invalid in 12 hours. Do not share it with anyone.

Reply to {support} if you have any questions.

If you did not make this request, email {support} since your account
might be compromised.

Do not reply to this email specifically, it will not work.

- {inst_name}, {main_url}
""",
        email_token=email_token,
    )

    return await send_email_to_user(
        user_id, "{inst_name} - account deactivation request", email_body
    )


async def send_password_reset_email(user_email: str, email_token):
    email_body = fmt_email(
        """This is an automated email from {inst_name}
about your password reset.

Please visit {main_url}/password_reset.html#{email_token} to
reset your password.

The link will be invalid in 30 minutes. Do not share the link with anyone else.
Nobody from support will ask you for this link.

Reply to {support} if you have any questions.

Do not reply to this email specifically, it will not work.

- {inst_name}, {main_url}
""",
        email_token=email_token,
    )

    return await send_email(
        user_email, "{inst_name} - password reset request", email_body
    )


async def send_datadump_email(user_id: int, dump_token: str):
    email_body = fmt_email(
        """This is an automated email from {inst_name}
about your data dump.

Visit {main_url}/api/dump/get?key={dump_token} to fetch your
data dump.

The URL will be invalid in 6 hours.
Do not share this URL. Nobody will ask you for this URL.

Send an email to {support} if any questions arise.
Do not reply to this automated email.

- {inst_name}, {main_url}
    """,
        dump_token=dump_token,
    )

    return await send_email_to_user(
        user_id, "{inst_name} - Your data dump is here!", email_body
    )
