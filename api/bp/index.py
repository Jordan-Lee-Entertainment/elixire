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
elixire - index routes
    Those routes can be used by anyone, they differ from misc
    because those provide public functionality (where as /api/hello
    isn't used by a client).
"""
from sanic import Blueprint, response

from ..common.auth import token_check, check_admin

bp = Blueprint('index')


@bp.get('/api/domains')
async def domainlist_handler(request):
    """Gets the domain list.

    Returns admin-only domains if an
    Authorization header is given.
    """

    # Only check if user's token is valid and their admin status
    # if they gave authorization.
    is_admin = False
    if 'Authorization' in request.headers:
        user_id = await token_check(request)
        is_admin = await check_admin(request, user_id, False)

    adm_string = "" if is_admin else "WHERE admin_only = false"
    domain_records = await request.app.db.fetch(f"""
    SELECT domain_id, domain
    FROM domains
    {adm_string}
    ORDER BY official DESC, domain_id ASC
    """)

    adm_string_official = "" if is_admin else "AND admin_only = false"
    official_domains = await request.app.db.fetch(f"""
    SELECT domain_id
    FROM domains
    WHERE official = true {adm_string_official}
    ORDER BY domain_id ASC
    """)

    # dear god
    official_domains = [x[0] for x in official_domains]

    return response.json({
        'domains': dict(domain_records),
        'officialdomains': official_domains
    })
