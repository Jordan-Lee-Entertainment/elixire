# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.bp.admin.audit_log_actions import Action
# from api.common.email import send_email

class AuditLog:
    """Audit log manager class"""
    def __init__(self, app):
        self.app = app

    async def send_email(self, subject, full_text):
        """Send an email to all admins."""
        admins = await self.app.db.fetch("""
        SELECT users.user_id
        FROM users
        JOIN admin_user_settings
          ON admin_user_settings.user_id = users.user_id
        WHERE (
            users.admin = true AND
            admin_user_settings.audit_log_emails = true
        )
        """)

        admins = [r['user_id'] for r in admins]

        for admin_id in admins:
            await send_user_email(
                self.app, admin_id,
                subject, full_text
            )
