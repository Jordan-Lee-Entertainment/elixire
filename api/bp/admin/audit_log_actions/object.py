# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.admin.audit_log import EditAction, DeleteAction
from api.models import File, Shorten

log = logging.getLogger(__name__)


async def _generic_get(action, object_id: int) -> dict:
    """Fetches a resource from the database and returns its json representation
    for audit log usage."""
    # TODO: make the action classes use file/shorten models directly
    if action.type == "file":
        resource_type = File
    elif action.type == "shorten":
        resource_type = Shorten
    else:
        raise TypeError("Object type specified in Action is invalid.")

    resource = await resource_type.fetch(object_id)

    # add 'type' so that the emails contain better info
    return {**{"type": action.type}, **resource.to_dict()}


class ObjectEditAction(EditAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self.type = object_type

    async def get_object(self, object_id):
        return await _generic_get(self, object_id)

    async def details(self):
        lines = [f"{self.type.capitalize()} ID {self.id} was edited."]

        for key, old, new in self.different_keys_items():
            lines.append(f"\t{key}: {old!r} => {new!r}")

        return lines


class ObjectDeleteAction(DeleteAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self.type = object_type

    async def get_object(self, object_id):
        return await _generic_get(self, object_id)

    async def details(self) -> list:
        object_type = self.type.capitalize()

        lines = [
            f"{object_type} with ID {self.id} was deleted.",
            f"{object_type} information:",
        ]

        for key, val in self.object.items():
            lines.append(f"\t{key}: {val!r}")

        return lines
