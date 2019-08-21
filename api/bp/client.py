# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from quart import Blueprint, request, current_app as app

from api.errors import BadInput

bp = Blueprint("client", __name__)
log = logging.getLogger(__name__)


@bp.before_app_request
async def before_request():
    """Check the request for the x-elixire-client header"""
    try:
        client = request.headers["x-elixire-client"]
        app.logger.info("request client: %r", client)
    except KeyError:
        if app.mode == "prod":
            raise BadInput("X-Elixire-Client header not found")
