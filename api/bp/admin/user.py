# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, request, jsonify, current_app as app

from api.errors import NotFound, BadInput
from api.schema import validate, ADMIN_MODIFY_USER

from api.common.email import (
    fmt_email,
    send_user_email,
    activate_email_send,
    uid_from_email,
    clean_etoken,
)
from api.common.auth import token_check, check_admin
from api.common.pagination import Pagination

from api.bp.profile import get_limits, delete_user

from api.bp.admin.audit_log_actions.user import UserEditAction, UserDeleteAction
from api.response import resp_empty

log = logging.getLogger(__name__)
bp = Blueprint("admin_user", __name__)


async def _user_resp_from_row(user_row):
    if not user_row:
        raise NotFound("User not found")

    user = dict(user_row)
    user["limits"] = await get_limits(app.db, user["user_id"])
    user["user_id"] = str(user["user_id"])

    return jsonify(user)


@bp.route("/<int:user_id>")
async def get_user_handler(user_id: int):
    """Get a user's details in the service."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    row = await app.db.fetchrow(
        """
    SELECT user_id, username, active, admin, domain, subdomain,
      consented, email, paranoid
    FROM users
    WHERE user_id=$1
    """,
        user_id,
    )

    return await _user_resp_from_row(row)


@bp.route("/by-username/<username>")
async def get_user_by_username(username: str):
    """Get a user object via their username instead of user ID."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    row = await app.db.fetchrow(
        """
    SELECT user_id, username, active, admin, domain, subdomain,
      consented, email, paranoid
    FROM users
    WHERE username = $1
    """,
        username,
    )

    return await _user_resp_from_row(row)


async def notify_activate(user_id: int):
    """Inform user that they got an account."""
    if not app.econfig.NOTIFY_ACTIVATION_EMAILS:
        return

    log.info(f"Sending activation email to {user_id}")

    body = fmt_email(
        app,
        """This is an automated email from {inst_name}
about your account request.

Your account has been activated and you can now log in
at {main_url}/login.html.

Welcome to {inst_name}!

Send an email to {support} if any questions arise.
Do not reply to this automated email.

- {inst_name}, {main_url}
    """,
    )

    subject = fmt_email(app, "{inst_name} - Your account is now active")
    resp_tup, user_email = await send_user_email(app, user_id, subject, body)

    resp, _ = resp_tup

    if resp.status == 200:
        log.info(f"Sent email to {user_id} {user_email}")
    else:
        log.error(f"Failed to send email to {user_id} {user_email}")


@bp.route("/activate/<int:user_id>", methods=["POST"])
async def activate_user(user_id: int):
    """Activate one user, given their ID."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    async with UserEditAction(request, user_id):
        result = await app.db.execute(
            """
        UPDATE users
        SET active = true
        WHERE user_id = $1
        """,
            user_id,
        )

        if result == "UPDATE 0":
            raise BadInput("Provided user ID does not reference any user.")

    await app.storage.invalidate(user_id, "active")
    await notify_activate(user_id)

    # TODO check success of notify_activate
    return "", 204


@bp.route("/activate_email/<int:user_id>", methods=["POST"])
async def activation_email(user_id):
    """Send an email to the user so they become able
    to activate their account manually."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    active = await app.db.fetchval(
        """
    SELECT active
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )

    if active is None:
        raise BadInput("Provided user_id does not reference any user")

    if active:
        raise BadInput("User is already active")

    # there was an invalidate() call which is unecessary
    # because its already invalidated on activate_user_from_email

    resp_tup, _email = await activate_email_send(app, user_id)
    resp, _ = resp_tup

    # TODO '', 204
    return jsonify({"success": resp.status == 200})


@bp.route("/api/activate_email")
async def activate_user_from_email():
    """Called when a user clicks the activation URL in their email."""
    try:
        email_token = request.args["key"]
    except KeyError:
        raise BadInput("no key provided")

    user_id = await uid_from_email(app, email_token, "email_activation_tokens")

    res = await app.db.execute(
        """
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """,
        user_id,
    )

    await app.storage.invalidate(user_id, "active")
    await clean_etoken(app, email_token, "email_activation_tokens")
    log.info(f"Activated user id {user_id}")

    return jsonify({"success": res == "UPDATE 1"})


@bp.route("/deactivate/<int:user_id>", methods=["POST"])
async def deactivate_user(user_id: int):
    """Deactivate one user, given its ID."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    async with UserEditAction(request, user_id):
        result = await app.db.execute(
            """
        UPDATE users
        SET active = false
        WHERE user_id = $1
        """,
            user_id,
        )

        if result == "UPDATE 0":
            raise BadInput("Provided user ID does not reference any user.")

    await app.storage.invalidate(user_id, "active")
    return "", 204


@bp.route("/search")
async def users_search():
    """New, revamped search endpoint."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    pagination = Pagination()

    args = request.args
    query = args.get("query")

    # default to TRUE so the query parses correctly, instead of giving empty
    # string
    active_query = "TRUE"
    active = args.get("active")
    query_args = []

    if active is not None:
        active_query = "active = $4"
        active = active != "false"
        query_args = [active]

    users = await app.db.fetch(
        f"""
    SELECT user_id, username, active, admin, consented,
           COUNT(*) OVER() as total_count
    FROM users
    WHERE
    {active_query}
    AND (
            $2 = ''
            OR (username LIKE '%'||$2||'%' OR user_id::text LIKE '%'||$2||'%')
        )
    ORDER BY user_id ASC
    LIMIT $3
    OFFSET ($1::integer * $3::integer)
    """,
        pagination.page,
        query or "",
        pagination.per_page,
        *query_args,
    )

    def map_user(record):
        row = dict(record)
        row["user_id"] = str(row["user_id"])
        del row["total_count"]
        return row

    results = list(map(map_user, users))
    total_count = 0 if not users else users[0]["total_count"]

    return jsonify(pagination.response(results, total_count=total_count))


# TODO i tried to pull a "generic" in here and it turned out to be shit.
async def _pu_check(db, db_name, user_id, payload, updated_fields, field, col=None):
    """Checks if the given field exists on payload.

    If it does exist, it will update the given database and column
    with the given value on the payload.

    Parameters
    ----------
    db
        Database connection.
    db_name: str
        Database to update on.
    user_id: int
        User id we are updating the row on.
    payload: dict
        Request's payload.
    updated_fields: list
        The list of currently updated fields, to give
        as a response on the request handler.
    field: str
        The field we want to search on the payload
        and add to updated_fields
    col: str, optional
        The column to update, in the case col != field.
    """

    # Yes, this function takes a lot of arguments,
    # read the comment block on modify_user to know why
    if not col:
        col = field

    # check if field exists
    val = payload.get(field)
    if val is not None:

        # if it does exist, update on database
        await db.execute(
            f"""
        UPDATE {db_name}
        SET {col} = $1
        WHERE user_id = $2
        """,
            val,
            user_id,
        )

        updated_fields.append(field)


@bp.route("/<int:user_id>", methods=["PATCH"])
async def modify_user(user_id):
    """Modify a user's information."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    payload = validate(await request.get_json(), ADMIN_MODIFY_USER)

    updated = []

    db = app.db

    # _pu_check serves as a template for the following code structure:
    #   X = payload.get(field)
    #   if X is not None:
    #     update db with field
    #     updated.append(field)

    async with UserEditAction(request, user_id):
        await _pu_check(db, "users", user_id, payload, updated, "email")
        await _pu_check(
            db, "limits", user_id, payload, updated, "upload_limit", "blimit"
        )
        await _pu_check(
            db, "limits", user_id, payload, updated, "shorten_limit", "shlimit"
        )

    return jsonify(updated)


@bp.route("/<int:user_id>", methods=["DELETE"])
async def del_user(user_id):
    """Delete a single user.

    File deletion happens in the background.
    """
    admin_id = await token_check()
    await check_admin(admin_id, True)

    active = await app.db.fetchval(
        """
    SELECT active
    FROM users
    WHERE user_id = $1
    """,
        user_id,
    )

    if active is None:
        raise BadInput("user not found")

    async with UserDeleteAction(request, user_id):
        await delete_user(user_id, True)

    return "", 204
