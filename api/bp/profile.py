# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

import asyncpg
from quart import Blueprint, request, current_app as app, jsonify

from api.errors import FailedAuth, FeatureDisabled, BadInput, APIError
from api.common.auth import token_check, password_check, pwd_hash, check_admin
from api.common.email import (
    gen_email_token,
    uid_from_email_token,
    clean_etoken,
    send_deletion_confirm_email,
    send_password_reset_email,
)
from api.schema import (
    validate,
    PATCH_PROFILE,
    DEACTIVATE_USER_SCHEMA,
    PASSWORD_RESET_SCHEMA,
    PASSWORD_RESET_CONFIRM_SCHEMA,
)
from api.common.user import delete_user, get_basic_user
from api.common.profile import get_limits, get_counts, get_dump_status
from api.common.domain import get_basic_domain
from api.common.auth import pwd_check

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


@bp.route("", methods=["GET"])
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


async def _try_domain_patch(user_id: int, domain_id: int) -> None:
    domain = await get_basic_domain(domain_id)

    if domain is None:
        raise BadInput("Unknown domain")

    if domain["admin_only"] and not await check_admin(user_id):
        raise FailedAuth("You can't use admin-only domains")

    await app.db.execute(
        """
        UPDATE users
        SET domain = $1
        WHERE user_id = $2
        """,
        domain_id,
        user_id,
    )


async def _check_password(user_id: int, payload: dict) -> None:
    """Check the password given in the request payload.

    Can raise:
     - BadInput if payload.password isn't provided
     - FailedAuth if the password isn't correct
     - ValueError when the given user isn't found
    """
    if "password" not in payload:
        raise BadInput("Password not provided")

    partial = await app.storage.auth_user_from_user_id(user_id)

    # NOTE that this shouldn't happen if your user_id comes off token_check()
    if partial is None:
        raise ValueError("Unknown user ID")

    await pwd_check(partial["password_hash"], payload["password"])


async def _try_email_patch(user_id: int, email: str) -> None:
    try:
        await app.db.execute(
            """
            UPDATE users
            SET email = $1
            WHERE user_id = $2
            """,
            email,
            user_id,
        )
    except asyncpg.UniqueViolationError:
        raise BadInput("Email is already being used by another user")


async def _try_username_patch(user_id: int, username: str) -> None:
    username = username.lower()

    # the old username is queried because we need to invalidate the respective
    # uid:<old_username> key in storage. just in case some other user wants the
    # username in the next 600 seconds
    old_username = await app.storage.get_username(user_id)

    try:
        await app.db.execute(
            """
            UPDATE users
            SET username = $1
            WHERE user_id = $2
            """,
            username,
            user_id,
        )
    except asyncpg.exceptions.UniqueViolationError:
        raise BadInput("Username is already taken")

    await app.storage.raw_invalidate(
        f"uid:{old_username}", f"uname:{user_id}", f"uid:{username}"
    )


@bp.route("", methods=["PATCH"])
async def change_profile_handler():
    if not app.econfig.PATCH_API_PROFILE_ENABLED:
        raise FeatureDisabled("Changing your profile is currently disabled")

    user_id = await token_check()
    payload = validate(await request.get_json(), PATCH_PROFILE)

    if "username" in payload:
        await _check_password(user_id, payload)
        await _try_username_patch(user_id, payload["username"])

    if "email" in payload:
        await _check_password(user_id, payload)
        await _try_email_patch(user_id, payload["email"])

    if "domain" in payload:
        await _try_domain_patch(user_id, payload["domain"])

    if "subdomain" in payload:
        await app.db.execute(
            """
            UPDATE users
            SET subdomain = $1
            WHERE user_id = $2
            """,
            payload["subdomain"],
            user_id,
        )

    if "shorten_domain" in payload:
        # TODO check validity of domain id inside payload.shorten_domain
        await app.db.execute(
            """
            UPDATE users
            SET shorten_domain = $1
            WHERE user_id = $2
            """,
            payload["shorten_domain"],
            user_id,
        )

    if "shorten_subdomain" in payload:
        await app.db.execute(
            """
            UPDATE users
            SET shorten_subdomain = $1
            WHERE user_id = $2
            """,
            payload["shorten_subdomain"],
            user_id,
        )

    if "paranoid" in payload:
        await app.db.execute(
            """
            UPDATE users
            SET paranoid = $1
            WHERE user_id = $2
            """,
            payload["paranoid"],
            user_id,
        )

    if "consented" in payload:
        await app.db.execute(
            """
            UPDATE users
            SET consented= $1
            WHERE user_id = $2
            """,
            payload["consented"],
            user_id,
        )

    if "new_password" in payload:
        await _check_password(user_id, payload)
        await _update_password(user_id, payload["new_password"])

    user = await get_basic_user(user_id)
    return jsonify(user)


@bp.route("", methods=["DELETE"])
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

    email_token = await gen_email_token(user_id, "email_deletion_tokens")

    log.info(f"Generated email hash {email_token} for account deactivation")

    await app.db.execute(
        """
        INSERT INTO email_deletion_tokens(hash, user_id)
        VALUES ($1, $2)
        """,
        email_token,
        user_id,
    )

    await send_deletion_confirm_email(user_id, email_token)
    return "", 204


@bp.route("/delete_confirm", methods=["POST"])
async def deactivate_user_from_email():
    """Actually deactivate the account."""
    try:
        cli_hash = request.args["url"]
    except KeyError:
        raise BadInput("No valid token provided.")

    user_id = await uid_from_email_token(cli_hash, "email_deletion_tokens")

    await delete_user(user_id, True)
    await clean_etoken(cli_hash, "email_deletion_tokens")

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

    email_token = await gen_email_token(user_id, "email_pwd_reset_tokens")

    await app.db.execute(
        """
        INSERT INTO email_pwd_reset_tokens (hash, user_id)
        VALUES ($1, $2)
        """,
        email_token,
        user_id,
    )

    await send_password_reset_email(user_email, email_token)
    return "", 204


@bp.route("/reset_password_confirm", methods=["POST"])
async def password_reset_confirmation():
    """Handle the confirmation of a password reset."""
    payload = validate(await request.get_json(), PASSWORD_RESET_CONFIRM_SCHEMA)
    token = payload["token"]
    new_pwd = payload["new_password"]

    user_id = await uid_from_email_token(token, "email_pwd_reset_tokens")

    # reset password
    await _update_password(user_id, new_pwd)
    await clean_etoken(token, "email_pwd_reset_tokens")

    return "", 204
