"""
    elixire - route decorators
"""

from .common_auth import token_check, check_admin

def admin_route(handler):
    async def new_handler(request, *args, **kwargs):
        admin_id = await token_check(request)

        # raise exception on non-admins
        await check_admin(request, admin_id, True)

        # if it is all good, call the old handler
        return await handler(request, admin_id, *args, **kwargs)

    return new_handler
