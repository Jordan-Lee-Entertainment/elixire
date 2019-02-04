# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.personal_stats import get_counts
from api.bp.admin.audit_log import (
    EditAction, DeleteAction
)

log = logging.getLogger(__name__)


async def get_user(conn, user_id) -> dict:
    """Get a user as a dictionary."""
    user = await conn.fetchrow("""
    SELECT username, active, email, consented, admin, paranoid,
        subdomain, domain,
        shorten_subdomain, shorten_domain
    FROM users
    WHERE user_id = $1
    """, user_id)

    if user is None:
        return {}

    duser = dict(user)

    limits = await conn.fetchrow("""
    SELECT blimit, shlimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    dlimits = dict(limits)

    return {**duser, **dlimits}


class UserEditAction(EditAction):
    async def get_object(self, user_id):
        return await get_user(self.app.db, user_id)

    async def details(self):
        if not self.different_keys():
            return False

        lines = [f'User {self.after["username"]} ({self._id}) was edited.']

        for key, old, new in self.different_keys_items():
            lines.append(f'\t - {key}: {old} => {new}')

        return lines


class UserDeleteAction(DeleteAction):
    async def get_object(self, user_id):
        user = await get_user(self.app.db, user_id)
        user.update(await get_counts(self.app.db, user_id))
        return user

    async def details(self) -> list:
        lines = [
            f'User ID {self._id} was deleted',
            'Domain information:',
        ]

        for key, val in self.object.items():
            lines.append(f'\t{key}: {val!r}')

        return lines
