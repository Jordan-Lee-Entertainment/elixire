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


async def _create_shorten(app, user_id):
    redir_id = get_snowflake()
    async with app.app_context():
        shortname, _ = await gen_user_shortname(user_id)

    await app.db.execute(
        """
        INSERT INTO shortens (shorten_id, filename,
            uploader, redirto, domain, subdomain)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        redir_id,
        shortname,
        user_id,
        "https://google.com",
        0,
        "w",
    )


async def do_list(test_cli_user, path: str, *, before=None, after=None):
    before = f"before={before}" if before is not None else ""
    after = f"&after={after}" if after is not None else ""

    resp = await test_cli_user.get(f"/api{path}{before}{after}")
    assert resp.status_code == 200
    rjson = await resp.json

    objects = rjson["files" if path.startswith("/files") else "shortens"]
    assert isinstance(objects, list)
    return [int(obj_data["id"]) for obj_data in objects]


async def test_file_list(test_cli_user):
    for _ in range(30):
        await _create_file(test_cli_user.app, test_cli_user["user_id"])

    ids = await do_list(test_cli_user, "/files?limit=20")
    assert all(a >= b for a, b in zip(ids, ids[1:]))

    last_id = ids[-1]

    # request 2: check if "pagination" works by selecting the last id and using
    # it in a new request, with it as before=
    ids = await do_list(test_cli_user, "/files?", before=last_id)
    assert last_id not in ids
    assert len(ids) == 10


async def test_shorten_list(test_cli_user):
    for _ in range(30):
        await _create_shorten(test_cli_user.app, test_cli_user["user_id"])

    ids = await do_list(test_cli_user, "/shortens?limit=20")
    assert all(a >= b for a, b in zip(ids, ids[1:]))

    last_id = ids[-1]

    # request 2: check if "pagination" works by selecting the last id and using
    # it in a new request, with it as before=
    ids = await do_list(test_cli_user, "/shortens?", before=last_id)
    assert last_id not in ids
    assert len(ids) == 10
