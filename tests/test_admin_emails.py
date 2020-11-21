# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from tests.common.generators import username

pytestmark = pytest.mark.asyncio


async def test_broadcast(test_cli_admin):
    subject = username()
    body = username()

    resp = await test_cli_admin.post(
        "/api/admin/broadcast", json={"subject": subject, "body": body}
    )
    assert resp.status_code == 204

    # TODO https://gitlab.com/elixire/elixire/-/issues/172
    # email = test_cli_admin.app._email_list[-1]
    # assert email["subject"] == subject
    # assert email["content"] == body


async def test_sendmail(test_cli_admin):
    subject = username()
    body = username()

    user = await test_cli_admin.create_user()

    resp = await test_cli_admin.post(
        f"/api/admin/email/{user.id}", json={"subject": subject, "body": body}
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert rjson["email"] == user.email

    email = test_cli_admin.app._email_list[-1]
    assert email["email"] == user.email
    assert email["subject"] == subject
    assert email["content"] == body