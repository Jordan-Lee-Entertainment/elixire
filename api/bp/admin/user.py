# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, request, jsonify, current_app as app

from api.errors import NotFound, BadInput
from api.schema import validate, ADMIN_MODIFY_USER

from api.common.email import (
    send_activation_email,
    send_activated_email,
    uid_from_email_token,
    clean_etoken,
)
from api.common.auth import token_check, check_admin
from api.common.pagination import Pagination

from api.common.user import delete_user

from api.bp.admin.audit_log_actions.user import UserEditAction, UserDeleteAction
from api.models import User

log = logging.getLogger(__name__)
bp = Blueprint("admin_user", __name__)


@bp.route("/<int:user_id>")
async def get_user_handler(user_id: int):
    """Get a user's details in the service."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    user = await User.fetch(user_id)
    if user is None:
        raise NotFound("User not found")

    user_dict = user.to_dict()
    user_dict["limits"] = await user.fetch_limits()
    user_dict["stats"] = await user.fetch_stats()

    return jsonify(user_dict)


@bp.route("/by-username/<username>")
async def get_user_by_username(username: str):
    """Get a user object via their username instead of user ID."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    user = await User.fetch_by(username=username)
    if user is None:
        raise NotFound("User not found")

    user_dict = user.to_dict()
    user_dict["limits"] = await user.fetch_limits()
    user_dict["stats"] = await user.fetch_stats()

    return jsonify(user.to_dict())


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
    await send_activated_email(user_id)
    return "", 204


@bp.route("/activate_email/<int:user_id>", methods=["POST"])
async def activation_email(user_id):
    """Send an email to the user so they become able
    to activate their account manually."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    user = await User.fetch(user_id)
    if user is None:
        raise BadInput("Provided user_id does not reference any user")

    if user.active:
        raise BadInput("User is already active")

    # there was an invalidate() call which is unecessary
    # because its already invalidated on activate_user_from_email

    await send_activation_email(user_id)
    return "", 204


@bp.route("/api/activate_email")
async def activate_user_from_email():
    """Called when a user clicks the activation URL in their email."""
    try:
        email_token = request.args["key"]
    except KeyError:
        raise BadInput("no key provided")

    user_id = await uid_from_email_token(email_token, "email_activation_tokens")

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
    log.info("Activated user id %d", user_id)

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

    user = await User.fetch(user_id)
    if user is None:
        raise NotFound("User not found")

    async with UserDeleteAction(request, user_id):
        await delete_user(user_id, True)

    return "", 204
