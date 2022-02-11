# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import functools
from .common.auth import token_check, check_admin


def auth_route(handler):
    """Declare an authenticated route."""

    @functools.wraps(handler)
    async def auth_route_wrapped(*args, **kwargs):
        user_id = await token_check()
        return await handler(user_id, *args, **kwargs)

    return auth_route_wrapped


def admin_route(handler):
    """Declare an admin route."""

    @functools.wraps(handler)
    async def admin_route_wrapped(*args, **kwargs):
        admin_id = await token_check()

        # raise exception on non-admins
        await check_admin(admin_id, True)

        # if it is all good, call the old handler
        return await handler(admin_id, *args, **kwargs)

    return admin_route_wrapped
