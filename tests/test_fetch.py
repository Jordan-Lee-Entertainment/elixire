import pytest

import sys
import os
import secrets
import random

sys.path.append(os.getcwd())

from elixire.run import app as mainapp
import elixire.tests.creds
from elixire.tests.common import token, username, login_normal


@pytest.yield_fixture
def app():
    yield mainapp


@pytest.fixture
def test_cli(loop, app, test_client):
    return loop.run_until_complete(test_client(app))


async def test_invalid_path(test_cli):
    fmts = ['jpg', 'png', 'jpeg', 'gif']
    invalid_shit = [f'{username()}.{random.choice(fmts)}' for _ in range(100)]

    for invalid in invalid_shit:
        resp = await test_cli.get(f'/i/{invalid}')
        assert resp.status == 404


async def test_invalid_path_thumbnail(test_cli):
    fmts = ['jpg', 'png', 'jpeg', 'gif']
    invalid_shit = [f'{username()}.{random.choice(fmts)}' for _ in range(1000)]

    for invalid in invalid_shit:
        prefix = random.choice(['s', 't', 'l', 'm'])
        resp = await test_cli.get(f'/t/{prefix}{invalid}')
        assert resp.status == 404

