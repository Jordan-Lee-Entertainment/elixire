# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

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
        'data': ciphertext_res.decode()
    })
