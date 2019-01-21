# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.common.utils import find_different_keys
from api.common.domain import get_domain_info

log = logging.getLogger(__name__)

from api.bp.admin.audit_log import Action, EditAction
from api.bp.personal_stats import get_counts


async def get_user(conn, user_id) -> dict:
    """Get a user dictionary"""
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


class UserEditCtx(EditAction):
    """Context for user edits."""
    async def _get_object(self, user_id):
        return await get_user(self.app.db, user_id)

    async def _text(self):
        # if no keys were actually edited, don't make it
        # an action.
        if not self.diff_keys:
            return False

        username = self._after['username']

        lines = [
            f'User {username} ({self._id}) was edited.'
        ]

        for key, old, new in self.iter_diff_keys:
            lines.append(
                f'\t - {key}: {old} => {new}'
            )

        return lines


class UserDeleteCtx(Action):
    """Context for a user delete."""
    def __init__(self, request, user_id):
        super().__init__(request)
        self.user_id = user_id
        self.user = None

    async def __aenter__(self):
        self.user = await get_user(self.app.db, self.user_id)
        self.user.update(await get_counts(self.app.db, self.user_id))

    async def _text(self) -> list:
        lines = [
            f'User ID {self._id} was deleted',
            'Domain information:'
        ]

        for key, val in self.user.items():
            lines.append(f'\t{key}: {val!r}')

        return lines
