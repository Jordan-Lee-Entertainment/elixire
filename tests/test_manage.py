# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import asyncio

import pytest

from manage.main import amain

pytestmark = pytest.mark.asyncio


async def test_help(event_loop, app):
    status = await amain(event_loop, app.econfig, [])
    assert status == 0
