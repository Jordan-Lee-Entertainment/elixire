# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import os
import tempfile

from ..api.snowflake import get_snowflake
from ..api.common.profile import gen_user_shortname

pytestmark = pytest.mark.asyncio


async def _create_file(app, user_id):
    file_id = get_snowflake()
    async with app.app_context():
        shortname, _ = await gen_user_shortname(user_id)

    fd, path = tempfile.mkstemp(suffix=".png", prefix="elix")
    os.close(fd)

    await app.db.execute(
        """
        INSERT INTO files (
            file_id, mimetype, filename,
            file_size, uploader, fspath, domain, subdomain
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        file_id,
        "image/png",
        shortname,
        0,
        user_id,
        path,
        0,
        "w",
    )


async def test_file_list(test_cli_user):
    for _ in range(110):
        await _create_file(test_cli_user.app, test_cli_user["user_id"])

    resp = await test_cli_user.get("/api/files")
    assert resp.status_code == 200
    rjson = await resp.json
    assert isinstance(rjson["files"], list)
    files = rjson["files"]

    file_ids = [int(filedata["id"]) for filedata in files]
    assert all(a >= b for a, b in zip(file_ids, file_ids[1:]))

    last_file_id = files[-1]["id"]
    # TODO request files with that as before
