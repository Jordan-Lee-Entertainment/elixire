# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, request

bp = Blueprint("cors", __name__)


@bp.after_app_request
async def set_cors_headers(resp):
    """Set CORS headers for response."""
    # TODO the sanic-cors config we used only applied cors to
    # /api/, /i/, /s/ and /t/. i took the liberty of making it applied to
    # all the routes

    origin = request.headers.get("Origin", "*")
    resp.headers["Access-Control-Allow-Origin"] = origin

    resp.headers[
        "Access-Control-Allow-Headers"
    ] = "*, Content-Type, Authorization, Origin"

    resp.headers[
        "Access-Control-Expose-Headers"
    ] = "X-Ratelimit-Limit, X-Ratelimit-Remaining, X-Ratelimit-Reset"

    resp.headers["Access-Control-Allow-Methods"] = resp.headers.get("allow", "*")

    return resp
