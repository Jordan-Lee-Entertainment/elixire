"""
elixire - admin routes
"""
import logging

from sanic import Blueprint, response

from api.decorators import admin_route
from api.schema import validate, ADMIN_SEND_BROADCAST
from api.common.email import fmt_email, send_user_email


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


async def _do_broadcast(app, subject, body):
    uids = await app.db.fetch("""
    SELECT user_id
    FROM users
    WHERE active = true
    """)

    for row in uids:
        user_id = row['user_id']
        resp, user_email = await send_user_email(app, user_id, subject, body)

        if resp.status != 200:
            log.warn(f'warning, could not send to {user_id} {user_email}')
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
        _do_broadcast(app, subject, body),
        'admin_broadcast'
    )

    return response.json({
        'success': True
    })
