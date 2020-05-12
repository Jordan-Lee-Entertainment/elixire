# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from typing import Union

from api.bp.admin.audit_log import Action, EditAction, DeleteAction
from api.models import Domain

log = logging.getLogger(__name__)


class DomainAddAction(Action):
    async def details(self) -> list:
        domain = await Domain.fetch(self["domain_id"])
        assert domain is not None

        owner = await domain.fetch_owner()
        owner_str = f"{owner.id} {owner.name}" if owner else "<no owner set>"

        return [
            "Domain data:",
            f"\tid: {domain.id}",
            f"\tname: {domain.domain}",
            f"\ttags: {','.join(t.id for t in domain.tags) or '<no tags>'}",
            f"\tpermissions number: {domain.permissions}\n",
            f"set owner on add: {owner_str}",
        ]

    def __repr__(self):
        return f'<DomainAddAction domain_id={self["domain_id"]}'


class DomainEditAction(EditAction):
    async def get_object(self, domain_id) -> dict:
        domain = await Domain.fetch(domain_id)
        assert domain is not None
        owner = await domain.fetch_owner()
        return {**domain.to_dict(), **{"owner_id": owner.id if owner else None}}

    async def details(self) -> Union[list, bool]:
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
        domain = await Domain.fetch(domain_id)
        assert domain is not None
        return await domain.fetch_info_dict()

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
