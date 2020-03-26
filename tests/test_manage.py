# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from manage.main import amain

from tests.common.generators import username

pytestmark = pytest.mark.asyncio


async def _run(test_cli_user, args):
    return await amain(
        test_cli_user.app.loop, test_cli_user.app.econfig, args, test=True
    )


async def test_help(event_loop, app):
    _, status = await amain(event_loop, app.econfig, [])
    assert status == 0


async def test_sendmail(test_cli_user):
    subject, body = username(), username()

    app, status = await _run(
        test_cli_user, ["sendmail", test_cli_user.user["username"], subject, body]
    )
    assert status == 0

    email = app._email_list[-1]
    assert email["subject"] == subject
    assert email["content"] == body
