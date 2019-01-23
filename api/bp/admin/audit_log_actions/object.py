# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

log = logging.getLogger(__name__)

from api.bp.admin.audit_log import Action, EditAction

from api.common.fetch import OBJ_MAPPING

class ObjectEditCtx(EditAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self._type = object_type

    async def _get_object(self, object_id):
        try:
            getter, _ = OBJ_MAPPING[self._type]
            return await getter(self.app.db, object_id)
        except KeyError:
            raise RuntimeError('Object type is invalid')

    async def _text(self):
        lines = [
            f'{self._type.capitalize()} ID {self._id} was edited.'
        ]

        for key, old, new in self.iter_diff_keys:
            lines.append(f'\t{key}: {old!r} => {new!r}')

        return lines

# TODO: make this a DeleteAction
class ObjectDeleteCtx(Action):
    def __init__(self, request, object_id, object_type):
        super().__init__(request)
        self._id = object_id
        self._type = object_type

    async def _get_object(self, object_id):
        # TODO
        pass
