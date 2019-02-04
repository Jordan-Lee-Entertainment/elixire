# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - admin routes
"""
import logging

from sanic import Blueprint, response

from api.decorators import admin_route
from api.schema import validate, ADMIN_SEND_BROADCAST
from api.common.email import fmt_email, send_user_email
from api.bp.admin.audit_log_actions.email import BroadcastAction

log = logging.getLogger(__name__)
bp = Blueprint('admin')


@bp.get('/api/admin/test')
@admin_route
async def test_admin(request, admin_id):
    """Get a json payload for admin users.

    This is just a test route.
    """
    return response.json({
        'admin': True
    })


async def _do_broadcast(request, subject, body):
    app = request.app

    uids = await app.db.fetch("""
    SELECT user_id
    FROM users
    WHERE active = true
    """)

    async with BroadcastAction(request) as ctx:
        ctx.update(subject=subject, body=body, usercount=len(uids))

    for row in uids:
        user_id = row['user_id']

        resp_tup, user_email = await send_user_email(
            app, user_id, subject, body)

        resp, resp_text = resp_tup

        if resp.status != 200:
            log.warning(
                'warning, could not send to %d %r: %d %r',
                user_id, user_email, resp.status, resp_text
            )

            continue

        log.info(f'sent broadcast to {user_id} {user_email}')

    log.info(f'Dispatched to {len(uids)} users')


@bp.post('/api/admin/broadcast')
@admin_route
async def email_broadcast(request, admin_id):
    app = request.app
    payload = validate(request.json, ADMIN_SEND_BROADCAST)

    subject, body = payload['subject'], payload['body']

    # format stuff just to make sure
    subject, body = fmt_email(app, subject), fmt_email(app, body)

    # we do it in the background for webscale
    app.sched.spawn(
        _do_broadcast(request, subject, body),
        'admin_broadcast'
    )

    return response.json({
        'success': True
    })
