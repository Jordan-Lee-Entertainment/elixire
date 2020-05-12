# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, current_app as app

bp = Blueprint("cors", __name__)


@bp.after_app_request
async def set_cors_headers(resp):
    """Set CORS headers for response."""
    # TODO the sanic-cors config we used only applied cors to
    # /api/, /i/, /s/ and /t/. i took the liberty of making it applied to
    # all the routes

    if app.mode.is_dev:
        # If we are in a development environment, allow all origins to
        # make requests.
        #
        # This is useful because if the root domain of the instance is named
        # `localhost:3000`, then requests coming from `localhost:3000` wouldn't
        # work -- the `Access-Control-Allow-Origin` isn't supposed to have a
        # port number.
        allowed_origin = "*"
    else:
        allowed_origin = app._root_domain

    resp.headers["Access-Control-Allow-Origin"] = allowed_origin

    resp.headers[
        "Access-Control-Allow-Headers"
    ] = "*, Content-Type, Authorization, Origin"

    resp.headers[
        "Access-Control-Expose-Headers"
    ] = "X-Ratelimit-Limit, X-Ratelimit-Remaining, X-Ratelimit-Reset"

    resp.headers["Access-Control-Allow-Methods"] = resp.headers.get("allow", "*")

    return resp


async def setup():
    """Setup the CORS blueprint by fetching the first domain from the instance,
    for the Access-Control-Allow-Origin header"""

    app._root_domain = await app.db.fetchval(
        """
        SELECT domain
        FROM domains
        WHERE domain_id = 0
        """
    )
