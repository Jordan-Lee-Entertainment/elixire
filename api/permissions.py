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
elixi.re - domain permission helper
"""
from .errors import BadInput, FeatureDisabled


class Permissions:
    """Hold bit positions for each permission."""
    SHORTEN = 0
    UPLOAD = 1


async def domain_permissions(app, domain_id: int, permission: Permissions,
                             raise_on_err=True) -> bool:
    """Check if the given domain matches a given permission.

    This is used to check if you can upload/shorten to a domain.
    """
    perm = await app.db.fetchval("""
    SELECT permissions
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    if not perm:
        raise BadInput('Domain not found')

    flag = perm & (1 << permission)

    if (not flag) and raise_on_err:
        raise FeatureDisabled(f'This domain has perm {permission} disabled')

    return bool(flag)
