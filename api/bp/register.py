# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re backend source code - register route

This also includes routes like recovering username from email.
"""

import asyncpg

from quart import Blueprint, jsonify, current_app as app, request
from dns import resolver

from ..errors import BadInput, FeatureDisabled
from ..schema import validate, REGISTRATION_SCHEMA, RECOVER_USERNAME
from ..common.email import send_email, fmt_email
from ..common.webhook import register_webhook
from api.common.user import create_user

bp = Blueprint("register", __name__)


async def send_register_email(email: str) -> bool:
    """Send an email about the signup."""
    _inst_name = app.econfig.INSTANCE_NAME

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
""",
    )

    resp, _ = await send_email(email, f"{_inst_name} - signup confirmation", email_body)

    return resp.status == 200


async def check_email(email: str):
    """Check if a given email has an MX record.

    This does not check if the result of the MX record query
    points to a server that handles actual email.
    """
    _, domain = email.split("@")

    try:
        # check dns, MX record
        await app.loop.run_in_executor(None, app.resolv.query, domain, "MX")
    except (resolver.Timeout, resolver.NXDOMAIN, resolver.NoAnswer):
        raise BadInput("Email domain resolution failed" "(timeout or does not exist)")


@bp.post("/register")
async def register_user():
    """Send an 'account registration request' to a certain
    discord webhook.

    Look into /api/admin/activate for registration acceptance.
    """
    if not app.econfig.REGISTRATIONS_ENABLED:
        raise FeatureDisabled("Registrations are currently disabled")

    payload = validate(await request.get_json(), REGISTRATION_SCHEMA)

    username = payload["username"].lower()
    password = payload["password"]
    discord_user = payload["discord_user"]
    email = payload["email"]

    await check_email(email)

    try:
        user = await create_user(username=username, password=password, email=email)
    except asyncpg.exceptions.UniqueViolationError:
        raise BadInput("Username or email already exist.")

    user_id = user["user_id"]

    # invalidate if anything happened before
    # just to make sure.
    await app.storage.raw_invalidate(f"uid:{username}")

    succ = await send_register_email(email)
    succ_wb = await register_webhook(
        app.econfig.USER_REGISTER_WEBHOOK, user_id, username, discord_user, email
    )

    return jsonify(
        {
            "user_id": str(user_id),
            "success": succ and succ_wb,
        }
    )


async def send_recover_uname(uname: str, email: str):
    email_body = fmt_email(
        """
This is an automated email from {inst_name} about
your username recovery.

Your username is {uname}.

 - {inst_name}, {main_url}
""",
        uname=uname,
    )

    resp, _ = await send_email(email, "username recovery", email_body)

    return resp.status == 200


@bp.post("/recover_username")
async def recover_username():
    payload = validate(await request.get_json(), RECOVER_USERNAME)

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
    succ = await send_recover_uname(row["username"], row["email"])

    return jsonify(
        {
            "success": succ,
        }
    )
