# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re backend source code - register route

This also includes routes like recovering username from email.
"""

import asyncpg
import logging

from quart import Blueprint, current_app as app, request, jsonify
from dns import resolver

from api.errors import BadInput, FeatureDisabled, EmailError
from api.schema import validate, REGISTRATION_SCHEMA, RECOVER_USERNAME
from api.common.email import send_register_email, send_username_recovery_email
from api.common.webhook import register_webhook
from api.common.user import create_user, delete_user
from api.models import User

log = logging.getLogger(__name__)
bp = Blueprint("register", __name__)


async def check_email(loop, email: str):
    """Check if a given email has an MX record.

    This does not check if the result of the MX record query
    points to a server that handles actual email.
    """
    _, domain = email.split("@")

    if getattr(app, "_test", False):
        return

    try:
        # check dns, MX record
        await loop.run_in_executor(None, app.resolv.query, domain, "MX")
    except (resolver.Timeout, resolver.NXDOMAIN, resolver.NoAnswer):
        raise BadInput("Email domain resolution failed" "(timeout or does not exist)")


@bp.route("/register", methods=["POST"])
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

    await check_email(app.loop, email)

    try:
        udata = await create_user(
            username, password, email, active=not app.econfig.REQUIRE_ACCOUNT_APPROVALS
        )
    except asyncpg.exceptions.UniqueViolationError:
        raise BadInput("Username or email already exist.")

    user_id = udata["user_id"]
    try:
        await send_register_email(email)
    except EmailError:
        log.warning("failed to send email, deleting user")
        await delete_user(user_id, delete=True)
        raise BadInput("Failed to send email.")

    await register_webhook(user_id, username, discord_user, email)
    return jsonify(
        {"user_id": user_id, "require_approvals": app.econfig.REQUIRE_ACCOUNT_APPROVALS}
    )


@bp.route("/recover_username", methods=["POST"])
async def recover_username():
    payload = validate(await request.get_json(), RECOVER_USERNAME)
    email = payload["email"]

    user = await User.fetch_by(email=email)

    if user is None:
        raise BadInput("Email not found")

    await send_username_recovery_email(user.name, user.email)
    return "", 204
