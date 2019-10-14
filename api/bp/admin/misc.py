# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - admin routes
"""
import logging

from quart import Blueprint, jsonify, current_app as app, request

from api.common.auth import token_check, check_admin
from api.schema import validate, ADMIN_SEND_BROADCAST
from api.common.email import fmt_email, send_email_to_user
from api.bp.admin.audit_log_actions.email import BroadcastAction

log = logging.getLogger(__name__)
bp = Blueprint("admin_misc", __name__)


@bp.route("/test")
async def test_admin():
    """Get a json payload for admin users.

    This is just a test route.
    """
    admin_id = await token_check()
    await check_admin(admin_id, True)
    return jsonify({"admin": True})


async def _do_broadcast(subject, body):
    uids = await app.db.fetch(
        """
        SELECT user_id
        FROM users
        WHERE active = true
        """
    )

    async with BroadcastAction() as ctx:
        ctx.update(subject=subject, body=body, usercount=len(uids))

    for row in uids:
        user_id = row["user_id"]

        email_ok, user_email = await send_email_to_user(user_id, subject, body)

        if not email_ok:
            log.warning("warning, could not send to %d %r", user_id, user_email)

            continue

        log.info(f"sent broadcast to %d %r", user_id, user_email)

    log.info("dispatched to %d users", len(uids))


@bp.route("/broadcast", methods=["POST"])
async def email_broadcast():
    admin_id = await token_check()
    await check_admin(admin_id, True)

    payload = validate(await request.get_json(), ADMIN_SEND_BROADCAST)

    subject, body = payload["subject"], payload["body"]

    # format stuff just to make sure
    subject, body = fmt_email(subject), fmt_email(body)

    # we do it in the background for webscale
    app.sched.spawn(_do_broadcast(subject, body), "admin_broadcast")
    return "", 204
