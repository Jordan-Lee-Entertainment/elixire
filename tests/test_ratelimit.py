# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import time
import asyncio
import pytest

from api.bp.ratelimit import setup_ratelimits
from api.common.banning import unban_ip, unban_user

pytestmark = pytest.mark.asyncio


async def _set_ratelimits(app, ratelimit):
    app.econfig.RATELIMITS = {"*": ratelimit}
    async with app.app_context():
        setup_ratelimits()


async def test_ratelimits(test_cli):
    try:
        await _set_ratelimits(test_cli.app, (2, 1))

        resp = await test_cli.get("/api/hello")
        assert resp.status_code == 200

        assert resp.headers["x-ratelimit-limit"] == "2"
        assert resp.headers["x-ratelimit-remaining"] == "0"
        assert "x-ratelimit-reset" in resp.headers

        # TODO validate x-ratelimit-reset?

        resp = await test_cli.get("/api/hello")
        assert resp.status_code == 429

        cur_ts = time.time()
        reset_ts = float(resp.headers["x-ratelimit-reset"])
        sleep_secs = reset_ts - cur_ts
        await asyncio.sleep(sleep_secs)

        resp = await test_cli.get("/api/hello")
        assert resp.status_code == 200
    finally:
        # We reset the ratelimits back to a big one because the app
        # fixture is session scoped, so it'll live throughout the lifetime of
        # the test suite, and that can cause some errors as functions expect
        # to be able to do requests indefnitely.
        await _set_ratelimits(test_cli.app, (10000, 1))


async def test_banning(test_cli):
    try:
        await _set_ratelimits(test_cli.app, (2, 1))
        test_cli.app.econfig.RL_THRESHOLD = 2
        async with test_cli.app.app_context():
            await unban_ip("127.0.0.1")

        resp = await test_cli.get("/api/hello")
        assert resp.status_code == 200

        assert resp.headers["x-ratelimit-limit"] == "2"
        assert resp.headers["x-ratelimit-remaining"] == "0"

        for _ in range(2):
            resp = await test_cli.get("/api/hello")
            assert resp.status_code == 429

        resp = await test_cli.get("/api/hello")
        assert resp.status_code == 420
    finally:
        await _set_ratelimits(test_cli.app, (10000, 1))
        async with test_cli.app.app_context():
            await unban_ip("127.0.0.1")


async def test_banning_userwide(test_cli_user):
    try:
        await _set_ratelimits(test_cli_user.app, (2, 1))
        test_cli_user.app.econfig.RL_THRESHOLD = 2
        async with test_cli_user.app.app_context():
            await unban_user(test_cli_user["user_id"])

        resp = await test_cli_user.get("/api/profile")
        assert resp.status_code == 200
        assert resp.headers["x-ratelimit-limit"] == "2"
        assert resp.headers["x-ratelimit-remaining"] == "0"

        for _ in range(2):
            resp = await test_cli_user.get("/api/profile")
            assert resp.status_code == 429

        resp = await test_cli_user.get("/api/profile")
        assert resp.status_code == 420

        # ensure ip is unbanned still
        resp = await test_cli_user.get("/api/hello", do_token=False)
        assert resp.status_code == 200
    finally:
        await _set_ratelimits(test_cli_user.app, (10000, 1))
        async with test_cli_user.app.app_context():
            await unban_user(test_cli_user["user_id"])
