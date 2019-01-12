# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from sanic import Blueprint, response

from api.decorators import admin_route
from api.schema import validate, ADMIN_SEND_BROADCAST
from api.common.email import fmt_email, send_user_email

bp = Blueprint('admin_settings')

@bp.get('/api/admin/settings')
@admin_route
async def get_admin_settings(request, admin_id):
    """Get own admin settings."""
    row = await request.app.db.fetchrow("""
    SELECT audit_log_emails
    FROM admin_user_settings
    WHERE user_id = $1
    """, admin_id)

    drow = None if row is None else dict(row)
    return response.json(drow)


@bp.patch('/api/admin/settings')
@admin_route
async def change_admin_settings(request, admin_id):
    """Change own admin settings."""
    audit_emails = bool(request.json['audit_log_emails'])

    await request.app.db.execute("""
    INSERT INTO admin_user_settings (user_id, audit_log_emails)
    VALUES ($1, $2)

    ON CONFLICT ON CONSTRAINT admin_user_settings_pkey
    DO UPDATE SET
        audit_log_emails = $2
    WHERE admin_user_settings.user_id = $1
    """, admin_id, audit_emails)

    return response.text('', status=204)
