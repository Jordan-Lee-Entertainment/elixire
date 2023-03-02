# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.bp.ratelimit import setup_ratelimits


async def set_global_ratelimit(app, ratelimit, ban_threshold):
    app.econfig.RATELIMITS["*"] = ratelimit
    app.econfig.RL_THRESHOLD = ban_threshold
    async with app.app_context():
        setup_ratelimits()


async def test_banning(test_cli_quick_user):
    # with the following configs (1/10 global ratelimit and 1 as RL_THRESHOLD)
    # 1st request works
    # 2nd request gets ratelimited
    # 3rd request gets banned as 420 (you are now banned!)
    # 4th request gets banned as 403 (already banned)
    # [.. continues to be banned until ban period ends ..]

    await set_global_ratelimit(test_cli_quick_user.app, (1, 10), 1)

    try:
        resp = await test_cli_quick_user.get("/api/profile")
        assert resp.status_code == 200
        resp = await test_cli_quick_user.get("/api/profile")
        assert resp.status_code == 429
        resp = await test_cli_quick_user.get("/api/profile")
        assert resp.status_code == 420
        resp = await test_cli_quick_user.get("/api/profile")
        assert resp.status_code == 403
    finally:
        await set_global_ratelimit(test_cli_quick_user.app, (10000, 1), 10)
