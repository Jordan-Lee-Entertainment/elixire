# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from tests.common.generators import png_data, username
from api.models import File, Shorten

pytestmark = pytest.mark.asyncio


async def test_fetch_file_and_shorten(test_cli_admin):
    elixire_file = await test_cli_admin.create_file("test.png", png_data(), "image/png")
    resp = await test_cli_admin.get(f"/api/admin/file/{elixire_file.shortname}")
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert elixire_file.id == int(rjson["file_id"])
    assert elixire_file.shortname == rjson["filename"]

    shorten = await test_cli_admin.create_shorten()
    resp = await test_cli_admin.get(f"/api/admin/shorten/{shorten.shortname}")
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert shorten.id == int(rjson["shorten_id"])
    assert shorten.shortname == rjson["filename"]


async def test_update_object_shortname(test_cli_admin):
    elixire_file = await test_cli_admin.create_file("test.png", png_data(), "image/png")
    new_shortname = username()

    resp = await test_cli_admin.patch(
        f"/api/admin/file/{elixire_file.id}", json={"shortname": new_shortname}
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, list)

    async with test_cli_admin.app.app_context():
        new_elixire_file = await File.fetch(elixire_file.id)

        # they're the same file id, but different shortnames. we never update
        # file ids.
        assert new_elixire_file.id == elixire_file.id
        assert new_elixire_file.shortname != elixire_file.shortname

    shorten = await test_cli_admin.create_shorten()
    new_shortname = username()

    resp = await test_cli_admin.patch(
        f"/api/admin/shorten/{shorten.id}", json={"shortname": new_shortname}
    )
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, list)

    async with test_cli_admin.app.app_context():
        new_shorten = await Shorten.fetch(shorten.id)
        assert new_shorten.id == shorten.id
        assert new_shorten.shortname != shorten.shortname


async def test_delete_object_shortname(test_cli_admin):
    elixire_file = await test_cli_admin.create_file("test.png", png_data(), "image/png")
    resp = await test_cli_admin.delete(f"/api/admin/file/{elixire_file.id}")
    assert resp.status_code == 200

    async with test_cli_admin.app.app_context():
        new_elixire_file = await File.fetch(elixire_file.id)
        assert new_elixire_file.deleted

    shorten = await test_cli_admin.create_shorten()
    resp = await test_cli_admin.delete(f"/api/admin/shorten/{shorten.id}")
    assert resp.status_code == 200

    async with test_cli_admin.app.app_context():
        new_shorten = await Shorten.fetch(shorten.id)
        assert new_shorten.deleted
