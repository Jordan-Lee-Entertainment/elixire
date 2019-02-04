# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.admin.audit_log import EditAction, DeleteAction
from api.common.fetch import OBJ_MAPPING

log = logging.getLogger(__name__)


async def _generic_get(action, object_id: int) -> dict:
    """Fetches an object (shorten or file) from the database from an action."""
    try:
        _, getter = OBJ_MAPPING[action.type]
        return await getter(action.app.db, object_id)
    except KeyError:
        raise TypeError('Object type specified in Action is invalid.')


class ObjectEditAction(EditAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self.type = object_type

    async def get_object(self, object_id):
        return await _generic_get(self, object_id)

    async def _text(self):
        lines = [f'{self.type.capitalize()} ID {self.id} was edited.']

        for key, old, new in self.different_keys_items():
            lines.append(f'\t{key}: {old!r} => {new!r}')

        return lines


class ObjectDeleteAction(DeleteAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self.type = object_type

    async def get_objects(self, object_id):
        return await _generic_get(self, object_id)

    async def details(self) -> list:
        object_type = self.type.capitalize()

        lines = [
            f'{object_type} with ID {self.id} was deleted.',
            f'{object_type} information:',
        ]

        for key, val in self.object.items():
            lines.append(f'\t{key}: {val!r}')

        return lines
