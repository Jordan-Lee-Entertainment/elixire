# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import pytest

from tests.common.generators import png_data

pytestmark = pytest.mark.asyncio


async def test_fetch_file(test_cli_admin):
    elixire_file = await test_cli_admin.create_file("test.png", png_data(), "image/png")
    resp = await test_cli_admin.get(f"/api/admin/file/{elixire_file.shortname}")
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson, dict)
    assert elixire_file.id == int(rjson["file_id"])
    assert elixire_file.shortname == rjson["filename"]
