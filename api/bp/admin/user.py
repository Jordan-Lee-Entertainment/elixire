# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, jsonify, request, current_app as app

from api.decorators import admin_route
from api.errors import NotFound, BadInput
from api.schema import validate, ADMIN_MODIFY_USER

from api.common.email import (
    fmt_email,
    send_user_email,
    activate_email_send,
    uid_from_email,
    clean_etoken,
)
from api.common.pagination import Pagination

from api.bp.profile import get_limits, delete_user

from api.bp.admin.audit_log_actions.user import UserEditAction, UserDeleteAction

log = logging.getLogger(__name__)
bp = Blueprint("admin_user", __name__)


@bp.get("/admin/users/<int:user_id>")
@admin_route
async def get_user_handler(admin_id, user_id: int):
    """Get a user's details in the service."""
    udata = await app.db.fetchrow(
        """
    SELECT user_id, username, active, admin, domain, subdomain,
      consented, email, paranoid
    FROM users
    WHERE user_id=$1
    """,
        user_id,
    )

    if not udata:
        raise NotFound("User not found")

    dudata = dict(udata)
    dudata["user_id"] = str(dudata["user_id"])
    dudata["limits"] = await get_limits(app.db, user_id)

    return jsonify(dudata)


async def notify_activate(user_id: int):
    """Inform user that they got an account."""
    if not app.cfg.NOTIFY_ACTIVATION_EMAILS:
        return

    log.info(f"Sending activation email to {user_id}")

    body = fmt_email(
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

    subject = fmt_email("{inst_name} - Your account is now active")
    resp_tup, user_email = await send_user_email(user_id, subject, body)

    resp, _ = resp_tup

    if resp.status == 200:
        log.info(f"Sent email to {user_id} {user_email}")
    else:
        log.error(f"Failed to send email to {user_id} {user_email}")


@bp.post("/admin/activate/<int:user_id>")
@admin_route
async def activate_user(admin_id, user_id: int):
    """Activate one user, given its ID."""
    async with UserEditAction(user_id):
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

    return jsonify(
        {
            "success": True,
            "result": result,
        }
    )


@bp.post("/admin/activate_email/<int:user_id>")
@admin_route
async def activation_email(admin_id, user_id):
    """Send an email to the user so they become able
    to activate their account manually."""
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

    resp_tup, _email = await activate_email_send(user_id)
    resp, _ = resp_tup

    return jsonify(
        {
            "success": resp.status == 200,
        }
    )


@bp.get("/activate_email")
async def activate_user_from_email():
    """Called when a user clicks the activation URL in their email."""
    try:
        email_token = str(request.args["key"])
    except (KeyError, TypeError):
        raise BadInput("no key provided")

    user_id = await uid_from_email(email_token, "email_activation_tokens")

    res = await app.db.execute(
        """
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """,
        user_id,
    )

    await app.storage.invalidate(user_id, "active")
    await clean_etoken(email_token, "email_activation_tokens")
    log.info(f"Activated user id {user_id}")

    return jsonify({"success": res == "UPDATE 1"})


@bp.post("/admin/deactivate/<int:user_id>")
@admin_route
async def deactivate_user(admin_id: int, user_id: int):
    """Deactivate one user, given its ID."""
    async with UserEditAction(user_id):
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

    return jsonify({"success": True, "result": result})


@bp.get("/admin/users/search")
@admin_route
async def users_search(admin_id):
    """New, revamped search endpoint."""
    args = request.args
    pagination = Pagination()

    active = args.get("active", True) != "false"
    query = args.get("query")

    users = await app.db.fetch(
        """
    SELECT user_id, username, active, admin, consented,
           COUNT(*) OVER() as total_count
    FROM users
    WHERE active = $1
    AND (
            $3 = ''
            OR (username LIKE '%'||$3||'%' OR user_id::text LIKE '%'||$3||'%')
        )
    ORDER BY user_id ASC
    LIMIT $4
    OFFSET ($2::integer * $4::integer)
    """,
        active,
        pagination.page,
        query or "",
        pagination.per_page,
    )

    def map_user(record):
        row = dict(record)
        row["user_id"] = str(row["user_id"])
        del row["total_count"]
        return row

    results = [map_user(u) for u in users]
    total_count = 0 if not users else users[0]["total_count"]

    return jsonify(pagination.response(results, total_count=total_count))


# === DEPRECATED ===
#  read https://gitlab.com/elixire/elixire/issues/61#note_91039503
# These routes are here to maintain compatibility with some of our
# utility software (admin panels)


@bp.get("/admin/listusers/<int:page>")
@admin_route
async def list_users_handler(admin_id, page: int):
    """List users in the service"""
    data = await app.db.fetch(
        """
    SELECT user_id, username, active, admin, domain,
      subdomain, email, paranoid, consented
    FROM users
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($1 * 20)
    """,
        page,
    )

    def _cnv(row):
        drow = dict(row)
        drow["user_id"] = str(row["user_id"])
        return drow

    return jsonify(list(map(_cnv, data)))


@bp.get("/admin/list_inactive/<int:page>")
@admin_route
async def inactive_users_handler(admin_id, page: int):
    data = await app.db.fetch(
        """
    SELECT user_id, username, active, admin, domain, subdomain,
      email, paranoid, consented
    FROM users
    WHERE active=false
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($1 * 20)
    """,
        page,
    )

    def _cnv(row):
        drow = dict(row)
        drow["user_id"] = str(row["user_id"])
        return drow

    return jsonify(list(map(_cnv, data)))


@bp.post("/admin/search/user/<int:page>")
@admin_route
async def search_user(user_id: int, page: int):
    """Search a user by pattern matching the username."""
    j = await request.get_json()
    try:
        pattern = str(j["search_term"])
    except (KeyError, TypeError, ValueError):
        raise BadInput("Invalid search_term")

    if not pattern:
        raise BadInput("Insert a pattern.")

    pattern = f"%{pattern}%"

    rows = await app.db.fetch(
        """
    SELECT user_id, username, active, admin, consented
    FROM users
    WHERE username LIKE $1 OR user_id::text LIKE $1
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($2 * 20)
    """,
        pattern,
        page,
    )

    res = []

    for row in rows:
        drow = dict(row)
        drow["user_id"] = str(drow["user_id"])
        res.append(drow)

    return jsonify(res)


# === END DEPRECATED ===


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


@bp.patch("/admin/user/<int:user_id>")
@admin_route
async def modify_user(admin_id, user_id):
    """Modify a user's information."""
    j = await request.get_json()
    payload = validate(j, ADMIN_MODIFY_USER)

    updated = []

    db = app.db

    # _pu_check serves as a template for the following code structure:
    #   X = payload.get(field)
    #   if X is not None:
    #     update db with field
    #     updated.append(field)

    async with UserEditAction(user_id):
        await _pu_check(db, "users", user_id, payload, updated, "email")
        await _pu_check(
            db, "limits", user_id, payload, updated, "upload_limit", "blimit"
        )
        await _pu_check(
            db, "limits", user_id, payload, updated, "shorten_limit", "shlimit"
        )

    return jsonify(updated)


@bp.delete("/admin/user/<int:user_id>")
@admin_route
async def del_user(admin_id, user_id):
    """Delete a single user.

    File deletion happens in the background.
    """
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

    async with UserDeleteAction(user_id):
        await delete_user(user_id, True)

    return jsonify({"success": True})
