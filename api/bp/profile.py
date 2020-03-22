# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from collections import defaultdict
from typing import Dict, List

from quart import Blueprint, request, current_app as app, jsonify

from api.errors import FeatureDisabled, BadInput
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
from api.common.user import delete_user
from api.common.profile import fetch_dumps, wrap_dump_violet_job_state
from api.common.auth import pwd_check
from api.models import User, Domain

bp = Blueprint("profile", __name__)
log = logging.getLogger(__name__)


async def _update_password(user_id: int, new_pwd: str):
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

    user = await User.fetch(user_id)
    assert user is not None

    user_dict = user.to_dict()

    if "bare" in request.args:
        return {key: user_dict[key] for key in user_dict if key in {"id", "name"}}

    user_dict["limits"] = await user.fetch_limits()
    user_dict["stats"] = await user.fetch_stats()

    violet_jobs = await fetch_dumps(user_id, current=True)
    user_dict["dump_status"] = wrap_dump_violet_job_state(
        violet_jobs[0] if violet_jobs else None
    )

    return jsonify(user_dict)


async def _try_domain_patch(user_id: int, domain_id: int) -> None:
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


async def _try_username_patch(user_id: int, username: str) -> None:
    username = username.lower()

    # the old username is queried because we need to invalidate the respective
    # uid:<old_username> key in storage. just in case some other user wants the
    # username in the next 600 seconds
    old_username = await app.storage.get_username(user_id)

    await app.db.execute(
        """
        UPDATE users
        SET username = $1
        WHERE user_id = $2
        """,
        username,
        user_id,
    )

    await app.storage.raw_invalidate(
        f"uid:{old_username}", f"uname:{user_id}", f"uid:{username}"
    )


def to_update(user: dict, payload: dict, field: str) -> bool:
    """Return if a given field is to be updated inside the payload."""
    if field not in payload:
        return False

    return user[field] != payload[field]


async def validate_semantics(user_id: int, payload: dict) -> dict:
    """Validate input errors in the payload."""
    errors: Dict[str, List[str]] = defaultdict(list)

    user_obj = await User.fetch(user_id)
    assert user_obj is not None
    user = user_obj.to_dict()

    _field_must_password = ("name", "email", "new_password")
    _field_must_unique_user = ("name", "email")

    for field in _field_must_password:
        if to_update(user, payload, field):
            await _check_password(user_id, payload)
            break

    for field in _field_must_unique_user:
        if not to_update(user, payload, field):
            continue

        existing_user = await app.db.fetchrow(
            "SELECT user_id FROM users WHERE "
            f"{'username' if field == 'name' else field} = $1",
            payload[field],
        )

        if existing_user is not None:
            msg = {
                "name": "Username is already taken",
                "email": "Email is already being used by another user",
            }[field]

            errors[field].append(msg)

    domain_fields = ("domain", "shorten_domain")
    for field in domain_fields:
        if not to_update(user, payload, field):
            continue

        domain = await Domain.fetch(payload[field])

        if domain is None:
            errors[field].append("Unknown domain")
        else:
            if domain.admin_only and not await check_admin(user_id):
                errors[field].append("You can't use admin-only domains")

    return errors


async def finish_update(conn, user_id: int, payload: dict):
    user = await User.fetch(user_id)
    assert user is not None
    user_dict = user.to_dict()

    if to_update(user_dict, payload, "name"):
        await _try_username_patch(user_id, payload["name"])

    _simple_fields = (
        "email",
        "subdomain",
        "shorten_domain",
        "shorten_subdomain",
        "paranoid",
        "consented",
    )

    for field in _simple_fields:
        if not to_update(user_dict, payload, field):
            continue

        table = "users" if field == "email" else "user_settings"

        await conn.execute(
            f"UPDATE {table} SET {field} = $1 WHERE user_id = $2",
            payload[field],
            user_id,
        )

    if to_update(user_dict, payload, "domain"):
        await _try_domain_patch(user_id, payload["domain"])

    if to_update(user_dict, payload, "new_password"):
        await _update_password(user_id, payload["new_password"])


@bp.route("", methods=["PATCH"])
async def change_profile_handler():
    if not app.econfig.PATCH_API_PROFILE_ENABLED:
        raise FeatureDisabled("Changing your profile is currently disabled")

    user_id = await token_check()
    payload = validate(await request.get_json(), PATCH_PROFILE)
    if "name" in payload:
        payload["name"] = payload["name"].lower()

    # check the semantic validity of payload before running UPDATEs
    errors = await validate_semantics(user_id, payload)
    if errors:
        raise BadInput("Bad payload", errors)

    async with app.db.acquire() as conn:
        async with conn.transaction():
            await finish_update(conn, user_id, payload)

    user = await User.fetch(user_id)
    assert user is not None
    return jsonify(user.to_dict())


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

    user = await User.fetch_by(username=username)
    if user is None:
        raise BadInput("User not found")

    email_token = await gen_email_token(user.id, "email_pwd_reset_tokens")

    await app.db.execute(
        """
        INSERT INTO email_pwd_reset_tokens (hash, user_id)
        VALUES ($1, $2)
        """,
        email_token,
        user.id,
    )

    await send_password_reset_email(user.email, email_token)
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
