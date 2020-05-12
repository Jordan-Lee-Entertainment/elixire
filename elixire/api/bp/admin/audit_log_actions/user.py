# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.admin.audit_log import EditAction, DeleteAction
from api.models import User

log = logging.getLogger(__name__)


class UserEditAction(EditAction):
    async def get_object(self, user_id: int) -> dict:
        user = await User.fetch(user_id)
        assert user is not None
        return user.to_dict()

    async def details(self):
        if not self.different_keys():
            return False

        lines = [f'User {self.after["name"]} ({self.id}) was edited.']

        for key, old, new in self.different_keys_items():
            lines.append(f"\t - {key}: {old} => {new}")

        return lines


class UserDeleteAction(DeleteAction):
    async def get_object(self, user_id: int) -> dict:
        user = await User.fetch(user_id)
        assert user is not None
        return {**user.to_dict(), **await user.fetch_stats()}

    async def details(self) -> list:
        lines = [f"User ID {self.id} was deleted", "Domain information:"]

        for key, val in self.object.items():
            lines.append(f"\t{key}: {val!r}")

        return lines
