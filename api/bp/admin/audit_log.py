# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.bp.admin.audit_log_actions import Action
# from api.common.email import send_email

class AuditLog:
    """Audit log manager class"""
    def __init__(self, app):
        self.app = app

    async def dispatch_action(self, action: Action):
        """Dispatch an action to admins."""
        pass
