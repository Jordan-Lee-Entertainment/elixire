# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.common.domain import get_domain_info
from api.bp.admin.audit_log import (
    Action, EditAction, DeleteAction
)

log = logging.getLogger(__name__)

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

class DomainEditCtx(EditAction):
    """Context for domain edits"""
    async def _get_object(self, domain_id) -> dict:
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

    async def _text(self):
        # if no keys were actually edited, don't make it
        # an action.
        if not self.diff_keys:
            return False

        domain = self._after['domain']

        lines = [
            f'Domain {domain} ({self._id}) was edited.'
        ]

        for key, old, new in self.iter_diff_keys:
            if key == 'owner_id':
                old_uname = await self.app.storage.get_username(old)
                old = f'{old} {old_uname}'

                new_uname = await self.app.storage.get_username(new)
                new = f'{new} {new_uname}'

            lines.append(
                f'\t - {key}: {old} => {new}'
            )

        return '\n'.join(lines)


class DomainRemoveCtx(DeleteAction):
    """Domain removal context."""

    async def _get_object(self, domain_id):
        return await get_domain_info(self.app.db, domain_id)

    async def _text(self) -> list:
        lines = [
            f'Domain ID {self._id} was deleted.',
            'Domain information:'
        ]

        for key, val in self._obj['info'].items():

            # special case for owner since its another dict
            if key == 'owner':
                uid = val['user_id']
                lines.append(f'\tinfo.{key}: {uid!r}')
                continue

            lines.append(f'\tinfo.{key}: {val!r}')

        for key, val in self._obj['stats'].items():
            lines.append(f'\tstats.{key}: {val!r}')

        for key, val in self._obj['public_stats'].items():
            lines.append(f'\tpublic_stats.{key}: {val!r}')

        return lines
