# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import logging
import asyncio
from typing import Optional

from quart import current_app as app, request

from api.common.email import send_user_email
from api.common.utils import find_different_keys

log = logging.getLogger(__name__)


class Action:
    """Represents a generic action taken by an admin."""

    def __init__(self):
        self.app = app
        self.admin_id = request.ctx[1]
        self.context = {}

    async def details(self):
        """Return the details of this action."""
        raise NotImplementedError()

    def update(self, **kwargs):
        """Update values of the context of this action."""
        self.context.update(kwargs)

    async def render(self) -> Optional[str]:
        """Return the full textual representation of this action."""

        try:
            action_text = await self.details()
        except NotImplementedError:
            action_text = "<no text set for action>"

        # actions can decide to "cancel themselves" if they return False
        # (this allows actions to only count as actions under certain conditions)
        if action_text is False:
            return None

        if isinstance(action_text, list):
            action_text = "\n".join(action_text)

        lines = [action_text, f"\naction context (for debugging purposes):"]

        for key, val in self.context.items():
            lines.append(f"\t{key!r}: {val!r}")

        # get admin via request ctx
        admin_id = self.admin_id
        admin_username = await self.app.storage.get_username(admin_id)
        lines.append(f"admin that performed the action: {admin_username} ({admin_id})")

        return "\n".join(lines)

    async def __aenter__(self):
        log.debug("entering context, action %s", self)
        return self

    async def __aexit__(self, type, value, traceback):
        # only notify when there are no errors happening inside the context
        log.debug("exiting context, action %s, exc=%s", self, value)
        if type is None and value is None and traceback is None:
            return await self.app.audit_log.push(self)

        return False

    def __contains__(self, item):
        return item in self.context

    def __getitem__(self, key):
        return self.context.get(key)

    def __repr__(self):
        return f"<Action admin_id={self.admin_id}>"


class EditAction(Action):
    """An action which describes an object is edited."""

    def __init__(self, _request, id):
        super().__init__()
        self.id = id
        self.before = None
        self.after = None

    async def get_object(self, id) -> dict:
        """Return the "associated object" with this action.

        It should be a plain dict.
        """
        raise NotImplementedError()

    async def __aenter__(self):
        self.before = await self.get_object(self.id)

    async def __aexit__(self, typ, value, traceback):
        self.after = await self.get_object(self.id)
        await super().__aexit__(typ, value, traceback)

    def different_keys(self) -> list:
        """Find the different keys between the before and after objects."""
        return find_different_keys(self.before, self.after)

    def different_keys_items(self):
        """Iterate old/new item pairs based on the diff_keys property."""
        for key in self.different_keys():
            yield key, self.before.get(key), self.after.get(key)


class DeleteAction(Action):
    """An action which describes the removal of an object."""

    def __init__(self, _request, id):
        super().__init__()
        self.id = id
        self.object = None

    async def get_object(self, id) -> dict:
        """Return the "associated object" with this action.

        It should be a plain dict.
        """
        raise NotImplementedError()

    async def __aenter__(self):
        self.object = await self.get_object(self.id)


class AuditLog:
    """Audit log manager class.

    This class manages a queue of actions. The log will only be sent to admins
    after a minute of queue inactivity.
    """

    def __init__(self, app):
        self.app = app
        self.actions = []
        self._sender_task = None

    def _reset(self):
        """Reset the sender task, causing the queue to be consumed in a minute."""
        if self._sender_task:
            self._sender_task.cancel()

        self._sender_task = self.app.sched.spawn(
            self._sender(), task_id="global_sender_task"
        )

    async def push(self, action: Action):
        """Push an action to the queue."""
        log.debug("[OwO] pushing action to queue: %s", action)
        self.actions.append(action)
        self._reset()

    async def _consume_and_process_queue(self):
        """Consume the queue, rendering all actions and sending the email."""
        if not self.actions:
            return

        # copy and wipe the current action queue
        actions = copy.copy(self.actions)
        self.actions = []

        action_count = len(actions)

        if action_count == 1:
            subject = "Audit Log"
        else:
            subject = f"Audit Log - {action_count} actions"

        rendered_actions = []

        # for each action, generate its full text for the email.
        for action in actions:
            text = await action.render()

            if text is None:
                continue

            rendered_actions.append(text)
            rendered_actions.append("\n")

        if not rendered_actions:
            return

        # construct full text from all of the rendered actions
        full = "\n".join(rendered_actions)
        await self.send_email(subject, full)

    async def _sender(self):
        try:
            await asyncio.sleep(60)
            await self._consume_and_process_queue()
        except asyncio.CancelledError:
            log.debug("cancelled send task")
        except Exception:
            log.exception("error while sending")

    async def send_email(self, subject, full_text):
        """Send an email to all admins."""
        admins = await self.app.db.fetch(
            """
        SELECT users.user_id
        FROM users
        JOIN admin_user_settings
          ON admin_user_settings.user_id = users.user_id
        WHERE (
            users.admin = true AND
            admin_user_settings.audit_log_emails = true
        )
        """
        )

        admins = [r["user_id"] for r in admins]

        log.info("sending audit log event to %d admins", len(admins))

        for admin_id in admins:
            await send_user_email(self.app, admin_id, subject, full_text)
