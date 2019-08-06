# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import random

from .common import username

pytestmark = pytest.mark.asyncio


async def test_invalid_path(test_cli):
    fmts = ["jpg", "png", "jpeg", "gif"]
    invalid_shit = [f"{username()}.{random.choice(fmts)}" for _ in range(100)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f"/i/{invalid}")
        assert resp.status_code == 404


async def test_invalid_path_thumbnail(test_cli):
    fmts = ["jpg", "png", "jpeg", "gif"]
    invalid_shit = [f"{username()}.{random.choice(fmts)}" for _ in range(100)]

    for invalid in invalid_shit:
        prefix = random.choice(["s", "t", "l", "m"])
        resp = await test_cli.get(f"/t/{prefix}{invalid}")
        assert resp.status_code == 404
