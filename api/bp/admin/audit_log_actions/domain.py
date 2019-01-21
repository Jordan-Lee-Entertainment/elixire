# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.common.utils import find_different_keys
from api.common.domain import get_domain_info

log = logging.getLogger(__name__)

from api.bp.admin.audit_log import Action


class DomainAddCtx(Action):
    """Context for a domain add."""
    def __repr__(self):
        return (f'<DomainAddAction '
                f'domain_id={self._ctx("domain_id")} '
                f'owner_id={self._ctx("owner_id")}>')

    async def _text(self):
        owner_id = self._ctx('owner_id')
        owner_name = await self.app.storage.get_username(owner_id)

        domain_id = self._ctx('domain_id')

        domain = await self.app.db.fetchrow("""
        SELECT domain, admin_only, official, permissions
        FROM domains
        WHERE domain_id = $1
        """, domain_id)

        lines = [
            'Domain data:',
            f'\tid: {domain_id}',
            f'\tname: {domain["domain"]}',
            f'\tis admin only? {domain["admin_only"]}',
            f'\tofficial? {domain["official"]}',
            f'\tpermissions number: {domain["permissions"]}\n',
            f'set owner on add: {owner_name} ({owner_id})'
        ]

        return '\n'.join(lines)

class DomainEditCtx(Action):
    """Context for domain edits"""
    def __init__(self, request, domain_id):
        super().__init__(request)
        self.domain_id = domain_id
        self._domain_before, self._domain_after = None, None

    async def _get_domain(self, domain_id) -> dict:
        """Get domain information as a dictionary"""
        domain = await self.app.db.fetchrow("""
        SELECT admin_only, official, domain, permissions
        FROM domains
        WHERE domain_id = $1
        """, domain_id)

        domain = dict(domain) if domain is not None else {}

        domain_owner = await self.app.db.fetchval("""
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """, domain_id)

        domain['owner_id'] = domain_owner

        return domain

    async def __aenter__(self):
        self._domain_before = await self._get_domain(self.domain_id)

    async def __aexit__(self, typ, value, traceback):
        self._domain_after = await self._get_domain(self.domain_id)
        await super().__aexit__(typ, value, traceback)

    async def _text(self):
        keys = find_different_keys(self._domain_before, self._domain_after)

        domain = self._domain_after['domain']

        lines = [
            f'Domain {domain} ({self.domain_id}) was edited.'
        ]

        for key in keys:
            # get the old and new value from before and after the edit
            # respectively
            old, new = self._domain_before[key], self._domain_after[key]

            if key == 'owner_id':
                old_uname = await self.app.storage.get_username(old)
                old = f'{old} {old_uname}'

                new_uname = await self.app.storage.get_username(new)
                new = f'{new} {new_uname}'

            lines.append(
                f'\t - {key}: {old} => {new}'
            )

        return '\n'.join(lines)


class DomainRemoveCtx(Action):
    """Domain removal context."""
    def __init__(self, request, domain_id):
        super().__init__(request)
        self.domain_id = domain_id
        self.domain = None

    async def __aenter__(self):
        self.domain = await get_domain_info(self.app.db, self.domain_id)

    async def __aexit__(self, typ, value, traceback):
        await super().__aexit__(typ, value, traceback)

    async def _text(self) -> list:
        lines = [
            f'Domain ID {self.domain_id} was deleted.',
            'Domain information:'
        ]

        for key, val in self.domain['info'].items():

            # special case for owner since its another dict
            if key == 'owner':
                uid = val['user_id']
                lines.append(f'\tinfo.{key}: {uid!r}')
                continue

            lines.append(f'\tinfo.{key}: {val!r}')

        for key, val in self.domain['stats'].items():
            lines.append(f'\tstats.{key}: {val!r}')

        for key, val in self.domain['public_stats'].items():
            lines.append(f'\tpublic_stats.{key}: {val!r}')

        return lines
