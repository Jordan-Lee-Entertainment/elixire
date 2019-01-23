# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from api.bp.admin.audit_log import Action

log = logging.getLogger(__name__)


class BroadcastAction(Action):
    async def _text(self):
        lines = [
            'An admin made a broadcast.',
            f'The broadcast had a subject of {self._ctx("subject")!r}.',
            f'It had {len(self._ctx("body"))} bytes in size.',
            f'It was broadcasted to {self._ctx("usercount")} users.',
        ]

        return lines
