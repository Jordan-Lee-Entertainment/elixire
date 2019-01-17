# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

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

        full_text = await self._make_full_text(action_text)
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

        domain = domain or {}

        domain_owner = await self.app.db.fetchval("""
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """, domain_id)

        domain['owner_id'] = domain_owner

    async def __aenter__(self):
        self._domain_before = await self._get_domain(self.domain_id)

    async def __aexit__(self, typ, value, traceback):
        self._domain_after = await self._get_domain(self.domain_id)
        super().__aexit__(typ, value, traceback)
