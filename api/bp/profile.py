# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio

import asyncpg

from quart import Blueprint, jsonify, request, current_app as app
from quart.ctx import copy_current_app_context

from ..errors import FailedAuth, FeatureDisabled, BadInput
from ..common.auth import (
    token_check,
    password_check,
    pwd_hash,
    check_admin,
    check_domain_id,
)
from api.common.email import (
    gen_email_token,
    send_user_email,
    uid_from_email,
    clean_etoken,
)
from ..schema import (
    validate,
    PROFILE_SCHEMA,
    DEACTIVATE_USER_SCHEMA,
    PASSWORD_RESET_SCHEMA,
    PASSWORD_RESET_CONFIRM_SCHEMA,
)
from ..common import delete_file
from ..common.utils import int_

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


async def get_limits(db, user_id) -> dict:
    """Get a user's limit information."""
    limits = await db.fetchrow(
        """
    SELECT blimit, shlimit
    FROM limits
    WHERE user_id = $1
    """,
        user_id,
    )

    if not limits:
        return {"limit": None, "used": None, "shortenlimit": None, "shortenused": None}

    bytes_used = await db.fetchval(
        """
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    AND file_id > time_snowflake(now() - interval '7 days')
    """,
        user_id,
    )

    shortens_used = await db.fetchval(
        """
    SELECT COUNT(*)
    FROM shortens
    WHERE uploader = $1
    AND shorten_id > time_snowflake(now() - interval '7 days')
    """,
        user_id,
    )

    return {
        "limit": limits["blimit"],
        "used": int_(bytes_used, 0),
        "shortenlimit": limits["shlimit"],
        "shortenused": shortens_used,
    }


@bp.get("/profile")
async def profile_handler():
    """Get your basic information as a user."""
    user_id = await token_check()
    user = await app.db.fetchrow(
        """
    SELECT user_id, username, active, email,
           consented, admin, subdomain, domain, paranoid,
           shorten_domain, shorten_subdomain
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )

    if not user:
        raise FailedAuth("unknown user")

    limits = await get_limits(app.db, user_id)

    duser = dict(user)
    duser["user_id"] = str(duser["user_id"])
    duser["limits"] = limits

    return jsonify(duser)


@bp.patch("/profile")
async def change_profile():
    """Change a user's profile."""
    if not app.econfig.PATCH_API_PROFILE_ENABLED:
        raise FeatureDisabled("changes on profile are currently disabled")

    user_id = await token_check()
    j = await request.get_json()
    payload = validate(j, PROFILE_SCHEMA)

    updated = []

    password = payload.get("password")
    new_pwd = payload.get("new_password")
    new_username = payload.get("username")

    new_domain = payload.get("domain")
    new_subdomain = payload.get("subdomain")

    new_shorten_subdomain = payload.get("shorten_subdomain")

    new_email = payload.get("email")
    new_paranoid = payload.get("paranoid")

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

    return jsonify(
        {
            "updated_fields": updated,
        }
    )


@bp.get("/limits")
async def limits_handler():
    """Query a user's limits."""
    user_id = await token_check()

    limits = await get_limits(app.db, user_id)

    return jsonify(limits)


@bp.delete("/account")
async def deactive_own_user():
    """Deactivate the current user.

    This does not delete right away for reasons.

    Sends an email to them asking for actual confirmation.
    """
    user_id = await token_check()
    j = await request.get_json()
    payload = validate(j, DEACTIVATE_USER_SCHEMA)
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
    res, _ = await send_user_email(
        user_id,
        f"{_inst_name} - account deactivation request",
        email_body,
    )
    resp, _ = res

    return jsonify({"success": resp.status == 200})


async def _delete_file_wrapper(shortname, user_id):
    lock = app.locks["delete_files"][user_id]
    await lock.acquire()

    try:
        await delete_file(shortname, user_id, False)
    finally:
        lock.release()

    return None


async def delete_file_task(user_id: int, delete=False):
    """Delete all the files from the user.

    Parameters
    ----------
    app: sanic.App
        App instance holding database connection
    user_id: int
        User ID to have all files deleted from.
    delete, optional: bool
        If delete the user when all files are deleted
    """
    file_shortnames = await app.db.fetch(
        """
    SELECT filename
    FROM files
    WHERE uploader = $1
    """,
        user_id,
    )

    log.info(f"Deleting ALL {len(file_shortnames)} files")

    tasks = []

    @copy_current_app_context
    async def _wrap(*args):
        await _delete_file_wrapper(*args)

    for row in file_shortnames:
        shortname = row["filename"]
        task = app.loop.create_task(_wrap(shortname, user_id))
        tasks.append(task)

    if tasks:
        await asyncio.gather(*tasks)

    log.info(f"finished waiting for {len(tasks)} tasks")
    log.info(f"delete? {delete}")

    if delete:
        log.info(f"Deleting user id {user_id}")
        await app.db.execute(
            """
        DELETE FROM users
        WHERE user_id = $1
        """,
            user_id,
        )


async def delete_user(user_id: int, delete=False):
    """Delete all user files.

    If the delete flag is set, it will delete the user record,
    else it'll mark the user as deactivated.

    Parameters
    ----------
    app: sanic.App
        Main app holding the database connection
    user_id: int
        User ID to delete.
    delete: bool, optional
        Delete the user records?
    """
    # ignore deletion of the dummy user via any admin-facing
    # administration util (manage.py will also be unable
    # to delete the dummy user).
    #  instance admins should proceed to deleting via the psql shell.
    if user_id == 0:
        log.warning("Not deleting dummy user")
        return

    old_active = await app.db.fetchval(
        """
        SELECT active FROM users WHERE user_id = $1
        """,
        user_id,
    )

    if not old_active:
        log.warning("User %d is already deactivated", user_id)
        return

    await app.db.execute(
        """
    UPDATE users
    SET active = false
    WHERE user_id = $1
    """,
        user_id,
    )

    await app.db.execute(
        """
    UPDATE files
    SET deleted = true
    WHERE uploader = $1
    """,
        user_id,
    )

    await app.db.execute(
        """
    UPDATE shortens
    SET deleted = true
    WHERE uploader = $1
    """,
        user_id,
    )

    await app.storage.invalidate(user_id, "active", "password_hash")

    @copy_current_app_context
    async def _wrap(*args):
        await delete_file_task(*args)

    # since there is a lot of db load
    # when calling delete_file, we create a task that deletes them.
    return app.sched.spawn(_wrap(user_id, delete), f"delete_files_{user_id}")


@bp.post("/delete_confirm")
async def deactivate_user_from_email():
    """Actually deactivate the account."""
    try:
        cli_hash = str(request.args["url"])
    except (KeyError, TypeError, ValueError):
        raise BadInput("No valid token provided.")

    user_id = await uid_from_email(cli_hash, "email_deletion_tokens")

    await delete_user(user_id, True)
    await clean_etoken(cli_hash, "email_deletion_tokens")

    log.warning(f"Deactivated user ID {user_id} by request.")

    return jsonify({"success": True})


@bp.post("/reset_password")
async def reset_password_req():
    """Send a password reset request."""
    j = await request.get_json()
    payload = validate(j, PASSWORD_RESET_SCHEMA)
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

    email_token = await gen_email_token(user_id, "email_pwd_reset_tokens")

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

    res, _ = await send_user_email(
        user_email, f"{_inst_name} - password reset request", email_body
    )
    resp, _ = res

    return jsonify({"success": resp.status == 200})


@bp.post("/reset_password_confirm")
async def password_reset_confirmation():
    """Handle the confirmation of a password reset."""
    j = await request.get_json()
    payload = validate(j, PASSWORD_RESET_CONFIRM_SCHEMA)
    token = payload["token"]
    new_pwd = payload["new_password"]

    user_id = await uid_from_email(token, "email_pwd_reset_tokens")

    # reset password
    await _update_password(user_id, new_pwd)
    await clean_etoken(token, "email_pwd_reset_tokens")

    return jsonify({"success": True})
