# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

import asyncpg
from quart import Blueprint, request, current_app as app, jsonify

from api.errors import FailedAuth, FeatureDisabled, BadInput, APIError
from api.common.auth import (
    token_check,
    password_check,
    pwd_hash,
    check_admin,
    check_domain_id,
)
from api.common.email import gen_email_token, send_email, uid_from_email, clean_etoken
from api.schema import (
    validate,
    PROFILE_SCHEMA,
    DEACTIVATE_USER_SCHEMA,
    PASSWORD_RESET_SCHEMA,
    PASSWORD_RESET_CONFIRM_SCHEMA,
)
from api.common.user import delete_user, get_basic_user
from api.common.profile import get_limits, get_counts, get_dump_status

bp = Blueprint("profile", __name__)
log = logging.getLogger(__name__)


async def _update_password(user_id, new_pwd):
    """Update a user's password."""
    new_hash = await pwd_hash(new_pwd)

    await app.db.execute(
        """
        UPDATE users
        SET password_hash = $1
        WHERE user_id = $2
    """,
        new_hash,
        user_id,
    )

    await app.storage.invalidate(user_id, "password_hash")


@bp.route("/profile", methods=["GET"])
async def profile_handler():
    """Get your basic information as a user."""
    user_id = await token_check()

    user = await get_basic_user(user_id)
    if user is None:
        raise FailedAuth("Unknown user")

    limits = await get_limits(user_id)
    if limits is None:
        raise APIError("Failed to fetch limits")

    user["limits"] = limits

    counts = await get_counts(user_id)
    user["stats"] = counts

    dump_status = await get_dump_status(user_id)
    user["dump_status"] = dump_status

    return jsonify(user)


@bp.route("/profile", methods=["PATCH"])
async def change_profile():
    """Change a user's profile."""
    if not app.econfig.PATCH_API_PROFILE_ENABLED:
        raise FeatureDisabled("changes on profile are currently disabled")

    user_id = await token_check()
    payload = validate(await request.get_json(), PROFILE_SCHEMA)

    updated = []

    password = payload.get("password")
    new_pwd = payload.get("new_password")
    new_username = payload.get("username")

    new_domain = payload.get("domain")
    new_subdomain = payload.get("subdomain")

    new_shorten_subdomain = payload.get("shorten_subdomain")

    new_email = payload.get("email")
    new_paranoid = payload.get("paranoid")

    # TODO simplify this code
    if password:
        await password_check(user_id, password)

    if password and new_username is not None:
        new_username = new_username.lower()

        # query the old username from database
        # instead of relying in Storage
        old_username = await app.db.fetchval(
            """
        SELECT username
        FROM users
        WHERE user_id = $1
        """,
            user_id,
        )

        try:
            await app.db.execute(
                """
            UPDATE users
            SET username = $1
            WHERE user_id = $2
            """,
                new_username,
                user_id,
            )
        except asyncpg.exceptions.UniqueViolationError:
            raise BadInput("Username already selected")

        # if this worked, we should invalidate the old keys
        await app.storage.raw_invalidate(f"uid:{old_username}", f"uname:{user_id}")

        # also invalidate the new one representing the future username
        await app.storage.raw_invalidate(f"uid:{new_username}")

        updated.append("username")

    if new_domain is not None:
        # Check if domain exists
        domain_info = await check_domain_id(new_domain)

        # Check if user has perms for getting that domain
        is_admin = await check_admin(user_id, False)
        if domain_info["admin_only"] and not is_admin:
            raise FailedAuth(
                "You're not an admin but you're "
                "trying to switch to an admin-only domain."
            )

        await app.db.execute(
            """
            UPDATE users
            SET domain = $1
            WHERE user_id = $2
        """,
            new_domain,
            user_id,
        )

        updated.append("domain")

    if new_subdomain is not None:
        await app.db.execute(
            """
            UPDATE users
            SET subdomain = $1
            WHERE user_id = $2
        """,
            new_subdomain,
            user_id,
        )

        updated.append("subdomain")

    # shorten_subdomain CAN be None.
    # when it is None, backend will assume the user wants the same domain
    # for both uploads and shortens
    try:
        new_shorten_domain = payload["shorten_domain"]
        await app.db.execute(
            """
            UPDATE users
            SET shorten_domain = $1
            WHERE user_id = $2
        """,
            new_shorten_domain,
            user_id,
        )

        updated.append("shorten_domain")
    except KeyError:
        pass

    if new_shorten_subdomain is not None:
        await app.db.execute(
            """
            UPDATE users
            SET shorten_subdomain = $1
            WHERE user_id = $2
        """,
            new_shorten_subdomain,
            user_id,
        )

        updated.append("shorten_subdomain")

    if password and new_email is not None:
        await app.db.execute(
            """
            UPDATE users
            SET email = $1
            WHERE user_id = $2
        """,
            new_email,
            user_id,
        )

        updated.append("email")

    if new_paranoid is not None:
        await app.db.execute(
            """
            UPDATE users
            SET paranoid = $1
            WHERE user_id = $2
        """,
            new_paranoid,
            user_id,
        )

        updated.append("paranoid")

    try:
        new_consent_state = payload["consented"]

        await app.db.execute(
            """
            UPDATE users
            SET consented = $1
            WHERE user_id = $2
        """,
            new_consent_state,
            user_id,
        )

        updated.append("consented")
    except KeyError:
        pass

    if password and new_pwd and new_pwd != password:
        # we are already good from password_check call
        await _update_password(user_id, new_pwd)
        updated.append("password")

    return jsonify({"updated_fields": updated})


@bp.route("/limits", methods=["GET"])
async def limits_handler():
    """Query a user's limits."""
    user_id = await token_check()
    limits = await get_limits(user_id)
    return jsonify(limits)


@bp.route("/account", methods=["DELETE"])
async def delete_own_user():
    """Deactivate the current user.

    This does not delete right away to make sure the user does not
    do it by accident.

    Sends an email to them asking for confirmation.
    """
    user_id = await token_check()

    # TODO unify all schemas that are just password into one?
    # do we have more than one?
    payload = validate(await request.get_json(), DEACTIVATE_USER_SCHEMA)
    await password_check(user_id, payload["password"])

    user_email = await app.db.fetchval(
        """
    SELECT email
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )

    if not user_email:
        raise BadInput("No email was found.")

    _inst_name = app.econfig.INSTANCE_NAME
    _support = app.econfig.SUPPORT_EMAIL

    email_token = await gen_email_token(app, user_id, "email_deletion_tokens")

    log.info(f"Generated email hash {email_token} for account deactivation")

    await app.db.execute(
        """
    INSERT INTO email_deletion_tokens(hash, user_id)
    VALUES ($1, $2)
    """,
        email_token,
        user_id,
    )

    email_body = f"""This is an automated email from {_inst_name}
about your account deletion.

Please visit {app.econfig.MAIN_URL}/deleteconfirm.html#{email_token} to
confirm the deletion of your account.

The link will be invalid in 12 hours. Do not share it with anyone.

Reply to {_support} if you have any questions.

If you did not make this request, email {_support} since your account
might be compromised.

Do not reply to this email specifically, it will not work.

- {_inst_name}, {app.econfig.MAIN_URL}
"""

    # TODO: change this to send user email?
    resp, _ = await send_email(
        app, user_email, f"{_inst_name} - account deactivation request", email_body
    )

    # TODO return '', 204
    return jsonify({"success": resp.status == 200})


@bp.route("/delete_confirm", methods=["POST"])
async def deactivate_user_from_email():
    """Actually deactivate the account."""
    try:
        cli_hash = request.args["url"]
    except KeyError:
        raise BadInput("No valid token provided.")

    # TODO rewrite email facilities
    user_id = await uid_from_email(app, cli_hash, "email_deletion_tokens")

    await delete_user(user_id, True)
    await clean_etoken(app, cli_hash, "email_deletion_tokens")

    log.warning(f"Deactivated user ID {user_id} by request.")

    return "", 204


@bp.route("/reset_password", methods=["POST"])
async def reset_password_req():
    """Send a password reset request."""
    payload = validate(await request.get_json(), PASSWORD_RESET_SCHEMA)
    username = payload["username"].lower()

    udata = await app.db.fetchrow(
        """
    SELECT email, user_id
    FROM users
    WHERE username = $1
    """,
        username,
    )

    if not udata:
        raise BadInput("User not found")

    user_email = udata["email"]
    user_id = udata["user_id"]

    _inst_name = app.econfig.INSTANCE_NAME
    _support = app.econfig.SUPPORT_EMAIL

    email_token = await gen_email_token(app, user_id, "email_pwd_reset_tokens")

    await app.db.execute(
        """
    INSERT INTO email_pwd_reset_tokens (hash, user_id)
    VALUES ($1, $2)
    """,
        email_token,
        user_id,
    )

    email_body = f"""This is an automated email from {_inst_name}
about your password reset.

Please visit {app.econfig.MAIN_URL}/password_reset.html#{email_token} to
reset your password.

The link will be invalid in 30 minutes. Do not share the link with anyone else.
Nobody from support will ask you for this link.

Reply to {_support} if you have any questions.

Do not reply to this email specifically, it will not work.

- {_inst_name}, {app.econfig.MAIN_URL}
"""

    resp, _ = await send_email(
        app, user_email, f"{_inst_name} - password reset request", email_body
    )

    # TODO return '', 204
    return jsonify({"success": resp.status == 200})


@bp.route("/reset_password_confirm", methods=["POST"])
async def password_reset_confirmation():
    """Handle the confirmation of a password reset."""
    payload = validate(await request.get_json(), PASSWORD_RESET_CONFIRM_SCHEMA)
    token = payload["token"]
    new_pwd = payload["new_password"]

    user_id = await uid_from_email(app, token, "email_pwd_reset_tokens")

    # reset password
    await _update_password(user_id, new_pwd)
    await clean_etoken(app, token, "email_pwd_reset_tokens")

    return "", 204
