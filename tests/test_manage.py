# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from manage.main import amain

from tests.common.generators import username, png_data
from api.models import File, Tag, Domain

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


async def test_find_inactive(test_cli_user):
    app, status = await _run(test_cli_user, ["find_inactive"])
    assert status == 0


async def test_find_unused(test_cli_user):
    app, status = await _run(test_cli_user, ["find_unused"])
    assert status == 0


async def test_file_operations(test_cli_user):

    # I'm not in the mood to add stdout checking and ensure that a new
    # file appears on the stats output. just making it sure it doesn't have
    # a type and executes well is enough.
    app, status = await _run(test_cli_user, ["stats"])
    assert status == 0

    sent_file = await test_cli_user.create_file("test.png", png_data(), "image/png")
    wanted_shortname = username()

    app, status = await _run(
        test_cli_user, ["rename_file", sent_file.shortname, wanted_shortname]
    )
    assert status == 0

    async with test_cli_user.app.app_context():
        wanted_file = await File.fetch_by(shortname=wanted_shortname)
        assert wanted_file is not None

    app, status = await _run(test_cli_user, ["delete", wanted_shortname])
    assert status == 0

    async with test_cli_user.app.app_context():
        wanted_file = await File.fetch_by(shortname=wanted_shortname)
        assert wanted_file.deleted


async def test_domain_operations(test_cli_user):
    domain = await test_cli_user.create_domain(f"{username()}.test")

    app, status = await _run(test_cli_user, ["list_domains"])
    assert status == 0

    tag_label = username()

    app, status = await _run(test_cli_user, ["create_tag", tag_label])
    assert status == 0

    async with test_cli_user.app.app_context():
        tags = await Tag.fetch_many_by(label=tag_label)
        assert tags

        tag = tags[0]

    try:
        app, status = await _run(
            test_cli_user, ["add_tag", str(domain.id), str(tag.id)]
        )
        assert status == 0

        async with test_cli_user.app.app_context():
            upstream_domain = await Domain.fetch(domain.id)
            assert upstream_domain is not None
            assert tag.id in [t.id for t in upstream_domain.tags]

        app, status = await _run(
            test_cli_user, ["remove_tag", str(domain.id), str(tag.id)]
        )
        assert status == 0

        app, status = await _run(test_cli_user, ["delete_tag", str(tag.id)])
        assert status == 0
    finally:
        async with test_cli_user.app.app_context():
            await tag.delete()
