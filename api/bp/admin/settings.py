# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from sanic import Blueprint, response

from api.decorators import admin_route
from api.schema import validate, ADMIN_SEND_BROADCAST
from api.common.email import fmt_email, send_user_email

bp = Blueprint('admin_settings')

@bp.patch('/api/admin/settings')
@admin_route
async def change_admin_settings(request, admin_id):
    """Change own admin settings."""
    audit_emails = bool(request.json['audit_log_emails'])

    await request.app.db.execute("""
    UPDATE admin_user_settings
    SET audit_log_emails = $1
    WHERE user_id = $2
    """, audit_emails, admin_id)

    return '', 204
