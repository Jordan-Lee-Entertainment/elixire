# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.common.utils import find_different_keys
from api.common.domain import get_domain_info

log = logging.getLogger(__name__)

from api.bp.admin.audit_log import Action, EditAction

class UserEditCtx(EditAction):
    """Context for user edits."""

    async def _get_object(self, user_id) -> dict:
        user = await self.app.db.fetchrow("""
        SELECT username, active, email, consented, admin, paranoid,
            subdomain, domain,
            shorten_subdomain, shorten_domain
        FROM users
        WHERE user_id = $1
        """, user_id)

        if user is None:
            return {}

        duser = dict(user)

        limits = await self.app.db.fetchrow("""
        SELECT blimit, shlimit
        FROM limits
        WHERE user_id = $1
        """, user_id)

        dlimits = dict(limits)

        return {**duser, **dlimits}

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
    pass
