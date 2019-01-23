# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.admin.audit_log import EditAction, DeleteAction
from api.common.fetch import OBJ_MAPPING

log = logging.getLogger(__name__)


async def _generic_get(ctx, object_id: int) -> dict:
    try:
        _, getter = OBJ_MAPPING[ctx.type]
        return await getter(ctx.app.db, object_id)
    except KeyError:
        raise RuntimeError('Object type is invalid')


class ObjectEditCtx(EditAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self.type = object_type

    async def _get_object(self, object_id):
        return await _generic_get(self, object_id)

    async def _text(self):
        lines = [
            f'{self.type.capitalize()} ID {self._id} was edited.'
        ]

        for key, old, new in self.iter_diff_keys:
            lines.append(f'\t{key}: {old!r} => {new!r}')

        return lines


class ObjectDeleteCtx(DeleteAction):
    def __init__(self, request, object_id, object_type):
        super().__init__(request, object_id)
        self.type = object_type

    async def _get_object(self, object_id):
        return await _generic_get(self, object_id)

    async def _text(self):
        otype = self.type.capitalize()
        lines = [
            f'{otype} ID {self._id} was deleted.',
            f'{otype} information:'
        ]

        for key, val in self._obj.items():
            lines.append(f'\t{key}: {val!r}')

        return lines
