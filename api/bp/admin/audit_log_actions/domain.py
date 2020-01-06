# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.common.domain import get_domain_info, get_domain_tag_ids
from api.bp.admin.audit_log import Action, EditAction, DeleteAction

log = logging.getLogger(__name__)


class DomainAddAction(Action):
    async def details(self):
        owner_id = self["owner_id"]
        domain_id = self["domain_id"]
        owner_name = await self.app.storage.get_username(owner_id)

        domain = await self.app.db.fetchrow(
            """
        SELECT domain, permissions
        FROM domains
        WHERE domain_id = $1
        """,
            domain_id,
        )

        lines = [
            "Domain data:",
            f"\tid: {domain_id}",
            f'\tname: {domain["domain"]}',
            f"\ttags: {await get_domain_tag_ids(domain_id)}",
            f'\tpermissions number: {domain["permissions"]}\n',
            f"set owner on add: {owner_name} ({owner_id})",
        ]

        return "\n".join(lines)

    def __repr__(self):
        return f'<DomainAddAction domain_id={self["domain_id"]} owner_id={self["owner_id"]}'


class DomainEditAction(EditAction):
    async def get_object(self, domain_id) -> dict:
        domain = await self.app.db.fetchrow(
            """
        SELECT domain, permissions
        FROM domains
        WHERE domain_id = $1
        """,
            domain_id,
        )

        domain = dict(domain) if domain is not None else {}

        domain_owner = await self.app.db.fetchval(
            """
        SELECT user_id
        FROM domain_owners
        WHERE domain_id = $1
        """,
            domain_id,
        )

        domain["owner_id"] = domain_owner

        domain["tags"] = await get_domain_tag_ids(domain_id)

        return domain

    async def details(self):
        # if no keys were actually edited, don't make it an action.
        if not self.different_keys():
            return False

        domain = self.after["domain"]

        lines = [f"Domain {domain} ({self.id}) was edited."]

        for key, old, new in self.different_keys_items():
            if key == "owner_id":
                old_uname = await self.app.storage.get_username(old)
                old = f"{old} {old_uname}"

                new_uname = await self.app.storage.get_username(new)
                new = f"{new} {new_uname}"

            lines.append(f"\t - {key}: {old} => {new}")

        return lines


class DomainRemoveAction(DeleteAction):
    async def get_object(self, domain_id):
        return await get_domain_info(domain_id)

    async def details(self) -> list:
        lines = [f"Domain ID {self.id} was deleted.", "Domain information:"]

        for key, val in self.object["info"].items():

            # special case for owner since its another dict
            if key == "owner" and val is not None:
                uid = val["user_id"]
                lines.append(f"\tinfo.{key}: {uid!r}")
                continue

            lines.append(f"\tinfo.{key}: {val!r}")

        for key, val in self.object["stats"].items():
            lines.append(f"\tstats.{key}: {val!r}")

        for key, val in self.object["public_stats"].items():
            lines.append(f"\tpublic_stats.{key}: {val!r}")

        return lines
