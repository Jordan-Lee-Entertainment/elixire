# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re backend source code - register route

This also includes routes like recovering username from email.
"""

import bcrypt
import asyncpg

from sanic import Blueprint, response
from dns import resolver

from ..snowflake import get_snowflake
from ..errors import BadInput, FeatureDisabled
from ..schema import validate, REGISTRATION_SCHEMA, RECOVER_USERNAME
from ..common.email import send_email, fmt_email
from ..common.webhook import register_webhook

bp = Blueprint("register")


async def send_register_email(app, email: str) -> bool:
    """Send an email about the signup."""
    _inst_name = app.econfig.INSTANCE_NAME

    email_body = fmt_email(
        app,
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
""",
    )

    resp, _ = await send_email(
        app, email, f"{_inst_name} - signup confirmation", email_body
    )

    return resp.status == 200


async def check_email(app, loop, email: str):
    """Check if a given email has an MX record.

    This does not check if the result of the MX record query
    points to a server that handles actual email.
    """
    _, domain = email.split("@")

    try:
        # check dns, MX record
        await loop.run_in_executor(None, app.resolv.query, domain, "MX")
    except (resolver.Timeout, resolver.NXDOMAIN, resolver.NoAnswer):
        raise BadInput("Email domain resolution failed" "(timeout or does not exist)")


@bp.post("/api/register")
async def register_user(request):
    """Send an 'account registration request' to a certain
    discord webhook.

    Look into /api/admin/activate for registration acceptance.
    """
    if not request.app.econfig.REGISTRATIONS_ENABLED:
        raise FeatureDisabled("Registrations are currently disabled")

    payload = validate(request.json, REGISTRATION_SCHEMA)

    username = payload["username"].lower()
    password = payload["password"]
    discord_user = payload["discord_user"]
    email = payload["email"]

    await check_email(request.app, request.app.loop, email)

    # borrowed from utils/adduser
    user_id = get_snowflake()

    _pwd = bytes(password, "utf-8")
    hashed = bcrypt.hashpw(_pwd, bcrypt.gensalt(14))

    try:
        await request.app.db.execute(
            """
        INSERT INTO users (user_id, username, password_hash, email, active)
        VALUES ($1, $2, $3, $4, false)
        """,
            user_id,
            username,
            hashed.decode("utf-8"),
            email,
        )
    except asyncpg.exceptions.UniqueViolationError:
        raise BadInput("Username or email already exist.")

    await request.app.db.execute(
        """
    INSERT INTO limits (user_id) VALUES ($1)
    """,
        user_id,
    )

    # invalidate if anything happened before
    # just to make sure.
    await request.app.storage.raw_invalidate(f"uid:{username}")

    app = request.app

    succ = await send_register_email(app, email)
    succ_wb = await register_webhook(
        app, app.econfig.USER_REGISTER_WEBHOOK, user_id, username, discord_user, email
    )

    return response.json(
        {
            "success": succ and succ_wb,
        }
    )


async def send_recover_uname(app, uname: str, email: str):
    email_body = fmt_email(
        app,
        """
This is an automated email from {inst_name} about
your username recovery.

Your username is {uname}.

 - {inst_name}, {main_url}
""",
        uname=uname,
    )

    resp, _ = await send_email(app, email, "username recovery", email_body)

    return resp.status == 200


@bp.post("/api/recover_username")
async def recover_username(request):
    payload = validate(request.json, RECOVER_USERNAME)
    app = request.app

    email = payload["email"]

    row = await app.db.fetchrow(
        """
    SELECT username, email
    FROM users
    WHERE email = $1
    LIMIT 1
    """,
        email,
    )

    if row is None:
        raise BadInput("Email not found")

    # send email
    succ = await send_recover_uname(app, row["username"], row["email"])

    return response.json(
        {
            "success": succ,
        }
    )
