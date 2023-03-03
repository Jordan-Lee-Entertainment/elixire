# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - admin routes
"""
import logging

from quart import Blueprint, request, jsonify, current_app as app

from api.decorators import admin_route
from api.schema import validate, ADMIN_SEND_BROADCAST
from api.common.email import fmt_email, send_user_email
from api.bp.admin.audit_log_actions.email import BroadcastAction

log = logging.getLogger(__name__)
bp = Blueprint("admin_misc", __name__)


@bp.get("/test")
@admin_route
async def test_admin(admin_id):
    """Get a json payload for admin users.

    This is just a test route.
    """
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

        resp_tup, user_email = await send_user_email(user_id, subject, body)

        resp, resp_text = resp_tup

        if resp.status != 200:
            log.warning(
                "warning, could not send to %d %r: %d %r",
                user_id,
                user_email,
                resp.status,
                resp_text,
            )

            continue

        log.info(f"sent broadcast to {user_id} {user_email}")

    log.info(f"Dispatched to {len(uids)} users")


@bp.post("/broadcast")
@admin_route
async def email_broadcast(admin_id):
    payload = validate(await request.get_json(), ADMIN_SEND_BROADCAST)

    subject, body = payload["subject"], payload["body"]

    # format stuff just to make sure
    subject, body = fmt_email(subject), fmt_email(body)

    # we do it in the background for webscale
    app.sched.spawn(_do_broadcast(subject, body), name="admin_broadcast")

    return jsonify({"success": True})
