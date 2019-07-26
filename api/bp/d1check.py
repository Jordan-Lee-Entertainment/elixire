# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, current_app as app, request, jsonify
from cryptography.fernet import Fernet, InvalidToken

from api.common import get_ip_addr
from api.errors import BadInput

bp = Blueprint('d1check', __name__)


@bp.route('/check', methods=['POST'])
async def d1_check():
    """Check endpoint for d1.

    Please look into d1's documentation
    on how d1's protocol works and how this code
    is a part of it.
    """
    try:
        j = await request.get_json()
        ciphertext = j['data']
    except (TypeError, KeyError):
        raise BadInput('Invalid json')

    fernet = Fernet(app.econfig.SECRET_KEY)

    try:
        data = fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise BadInput('Invalid ciphertext')

    ipaddr = get_ip_addr()
    data2 = f'{data},{ipaddr}'

    ciphertext_res = fernet.encrypt(data2.encode())

    return jsonify({
        'data': ciphertext_res
    })
