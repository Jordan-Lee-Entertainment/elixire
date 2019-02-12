# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.admin.audit_log import Action

log = logging.getLogger(__name__)


class BroadcastAction(Action):
    async def details(self) -> list:
        return [
            'An admin made a global broadcast.',
            f'The broadcast had a subject of {self["subject"]!r}.',
            f'It had {len(self["body"])} bytes in size.',
            f'It was broadcasted to {self["usercount"]} users.',
        ]


class DomainOwnerNotifyAction(Action):
    async def details(self) -> list:
        domain_id = self['domain_id']
        domain = await self.app.db.fetchval("""
        SELECT domain FROM domains WHERE domain_id = $1
        """, domain_id)

        user_id = self['user_id']
        user = await self.app.storage.get_username(user_id)

        return [
            'An admin notified the owner of a domain.',
            f'Domain: {domain_id}, {domain!r}',
            f'Owner was {user_id}, {user}'
            f'The broadcast had a subject of {self["subject"]!r}.',
            f'It had {len(self["body"])} bytes in size.',
        ]
