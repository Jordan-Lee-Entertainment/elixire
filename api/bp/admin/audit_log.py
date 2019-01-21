# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.common.email import send_user_email

log = logging.getLogger(__name__)


class Action:
    """Represents a generic action."""
    def __init__(self, request):
        self.app = request.app
        self.admin_id = request['_ctx_admin_id']
        self.context = {}

    def insert(self, **kwargs):
        """Insert values to an action's context"""
        for key, value in kwargs.items():
            self.context[key] = value

    def _ctx(self, key):
        return self.context.get(key)

    def __repr__(self):
        return f'<Action context={self.context}>'

    async def _make_full_text(self, action_text):
        lines = [
            'This is an automated email by the audit log subsystem.\n',
            'This is the full text given by the action object:',
            action_text,
            f'\naction: {self}',
        ]

        # get admin via request ctx
        admin_id = self.admin_id
        admin_uname = await self.app.storage.get_username(admin_id)
        lines.append(f'admin that made the action: {admin_uname} ({admin_id})')

        return '\n'.join(lines)

    async def _notify(self):
        """Dispatch this action to Admin users that are supposed to receive
        the action, as an email."""
        audit_log = self.app.audit_log

        # generate the email subject and text
        try:
            subject = self._subject
        except AttributeError:
            subject = 'Audit log action'

        try:
            action_text = await self._text()
        except AttributeError:
            action_text = '<No text set for action>'

        if isinstance(action_text, list):
            action_text = '\n'.join(action_text)

        full_text = await self._make_full_text(action_text)
        log.debug('full text: %r', full_text)
        await audit_log.send_email(subject, full_text)

    async def __aenter__(self):
        log.debug('entering context, action %s', self)
        return self

    async def __aexit__(self, typ, value, traceback):
        # only notify when there are no errors happening inside
        # the context
        log.debug('exiting context, action %s, exc=%s', self, value)
        if typ is None and value is None and traceback is None:
            return await self._notify()

        return False


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

        log.info('sending audit log event to %d admins', len(admins))

        for admin_id in admins:
            await send_user_email(
                self.app, admin_id,
                subject, full_text
            )
