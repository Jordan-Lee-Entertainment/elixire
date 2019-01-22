# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
import asyncio

from api.common.email import send_user_email
from api.common.utils import find_different_keys

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
            action_text,
            f'\naction: {self}',
        ]

        # get admin via request ctx
        admin_id = self.admin_id
        admin_uname = await self.app.storage.get_username(admin_id)
        lines.append(f'admin that made the action: {admin_uname} ({admin_id})')

        return '\n'.join(lines)

    async def _get_text(self):
        try:
            action_text = await self._text()
        except AttributeError:
            action_text = '<No text set for action>'

        if isinstance(action_text, list):
            action_text = '\n'.join(action_text)

        return action_text

    async def full_text(self) -> str:
        """Get full text"""
        action_text = await self._get_text()

        # actions can tell that they aren't worthy of
        # having an email by returning False as their
        # action text
        if action_text is False:
            return

        return await self._make_full_text(action_text)

    async def __aenter__(self):
        log.debug('entering context, action %s', self)
        return self

    async def __aexit__(self, typ, value, traceback):
        # only notify when there are no errors happening inside
        # the context
        log.debug('exiting context, action %s, exc=%s', self, value)
        if typ is None and value is None and traceback is None:
            return await self.app.audit_log.push(self)

        return False


class EditAction(Action):
    """Specifies an action where a certain object
    has been edited."""
    def __init__(self, request, identifier):
        super().__init__(request)
        self._id = identifier
        self._before, self._after = None, None

    async def _get_object(self, _identifier) -> dict:
        raise NotImplementedError()

    async def __aenter__(self):
        self._before = await self._get_object(self._id)

    async def __aexit__(self, typ, value, traceback):
        self._after = await self._get_object(self._id)
        await super().__aexit__(typ, value, traceback)

    @property
    def diff_keys(self) -> list:
        """Find the different keys between
        the before and after objects."""
        return find_different_keys(
            self._before, self._after
        )

    @property
    def iter_diff_keys(self):
        """Iterate old/new item pairs based on
        the diff_keys property."""
        for key in self.diff_keys:
            yield key, self._before.get(key), self._after.get(key)


class AuditLog:
    """Audit log manager class.

    This manages a queue of actions. The Log will only be actually sent
    out to admins after a minute of queue inactivity.
    """
    def __init__(self, app):
        self.app = app
        self.actions = []
        self._send_task = None

    def _reset(self):
        """Resets the send task"""
        if self._send_task:
            self._send_task.cancel()

        self._send_task = self.app.loop.create_task(self._send_task_func())

    async def push(self, action: Action):
        """Push an action to the queue."""
        self.actions.append(action)
        self._reset()

    async def _actual_send(self):
        # copy and wipe the current action queue
        actions = list(self.actions)
        self.actions = []

        if not actions:
            return

        action_count = len(actions)

        subject = ('Audit Log'
                   if action_count == 1 else
                   f'Audit Log - {action_count} actions')

        texts = []

        # for each action, generate its full text for the email.
        for action in actions:
            text = await action.full_text()

            if text is None:
                continue

            texts.append(text)
            texts.append('\n')

        if not texts:
            return

        # construct full text
        full = '\n'.join(texts)
        await self.send_email(subject, full)

    async def _send_task_func(self):
        try:
            await asyncio.sleep(60)
            await self._actual_send()
        except asyncio.CancelledError:
            log.warning('send task func err')
        except Exception:
            log.exception('error while sending')

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
