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

from sanic import Blueprint, response

from cryptography.fernet import Fernet, InvalidToken

from ..common import get_ip_addr
from ..errors import BadInput

bp = Blueprint(__name__)


@bp.post('/api/check')
async def d1_check(request):
    """Check endpoint for d1.

    Please look into d1's documentation
    on how d1's protocol works and how this code
    is a part of it.
    """
    try:
        ciphertext = request.json['data']
    except (TypeError, KeyError):
        raise BadInput('Invalid json')

    fernet = Fernet(request.app.econfig.SECRET_KEY)

    try:
        data = fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise BadInput('Invalid ciphertext')

    ipaddr = get_ip_addr(request)
    data2 = f'{data},{ipaddr}'

    ciphertext_res = fernet.encrypt(data2.encode())

    return response.json({
        'data': ciphertext_res
    })
