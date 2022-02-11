# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from manage.main import amain
from .test_upload import png_request
from .common import login_normal, username

pytestmark = pytest.mark.asyncio


async def _run(test_cli, args):
    return await amain(test_cli.app.loop, test_cli.app.econfig, args, is_testing=True)


async def test_help(event_loop, app):
    _, status = await amain(event_loop, app.econfig, [])
    assert status == 0


@pytest.mark.skip(reason="todo port sendmail from v3")
async def test_sendmail(test_cli):
    subject, body = username(), username()

    app, status = await _run(
        test_cli, ["sendmail", test_cli.user["username"], subject, body]
    )
    assert status == 0

    email = app._test_email_list[-1]
    assert email["subject"] == subject
    assert email["content"] == body


async def test_find_inactive(test_cli):
    app, status = await _run(test_cli, ["find_inactive"])
    assert status == 0


async def test_find_unused(test_cli):
    app, status = await _run(test_cli, ["find_unused"])
    assert status == 0


async def test_file_operations(test_cli):
    # I'm not in the mood to add stdout checking and ensure that a new
    # file appears on the stats output. just making it sure it didn't crash is
    # good enough
    app, status = await _run(test_cli, ["stats"])
    assert status == 0

    utoken = await login_normal(test_cli)
    kwargs = png_request()
    kwargs["headers"]["authorization"] = utoken
    resp = await test_cli.post(
        "/api/upload",
        **kwargs,
    )
    assert resp.status_code == 200
    elixire_file = await resp.json

    old_shortname = elixire_file["shortname"]
    new_shortname = username()

    app, status = await _run(test_cli, ["rename_file", old_shortname, new_shortname])
    assert status == 0

    # -- assert new shortname exists
    resp = await test_cli.get(
        "/api/list?page=0",
        headers={
            "authorization": utoken,
        },
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert new_shortname in rjson["files"]
    assert old_shortname not in rjson["files"]

    # -- delete it
    app, status = await _run(test_cli, ["delete", new_shortname])
    assert status == 0

    # -- assert new shortname doesnt exist
    resp = await test_cli.get(
        "/api/list?page=0",
        headers={
            "authorization": utoken,
        },
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert new_shortname not in rjson["files"]
    assert old_shortname not in rjson["files"]
