# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import secrets
import random

from .common import token, username, login_normal


async def test_invalid_path(test_cli):
    fmts = ['jpg', 'png', 'jpeg', 'gif']
    invalid_shit = [f'{username()}.{random.choice(fmts)}' for _ in range(100)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f'/i/{invalid}')
        assert resp.status == 404


async def test_invalid_path_thumbnail(test_cli):
    fmts = ['jpg', 'png', 'jpeg', 'gif']
    invalid_shit = [f'{username()}.{random.choice(fmts)}' for _ in range(100)]

    for invalid in invalid_shit:
        prefix = random.choice(['s', 't', 'l', 'm'])
        resp = await test_cli.get(f'/t/{prefix}{invalid}')
        assert resp.status == 404
