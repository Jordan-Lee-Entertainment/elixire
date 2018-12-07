"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

"""
    elixire - route decorators
"""

from .common.auth import token_check, check_admin


def auth_route(handler):
    """Declare an authenticated route."""
    async def _handler(request, *args, **kwargs):
        user_id = await token_check(request)
        return await handler(request, user_id, *args, **kwargs)

    return _handler


def admin_route(handler):
    """Declare an admin route."""
    async def _handler(request, *args, **kwargs):
        admin_id = await token_check(request)

        # raise exception on non-admins
        await check_admin(request, admin_id, True)

        # if it is all good, call the old handler
        return await handler(request, admin_id, *args, **kwargs)

    return _handler
