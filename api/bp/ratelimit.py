# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from dataclasses import dataclass
from typing import Optional

from quart import Blueprint, request, current_app as app
from ..ratelimit import RatelimitManager, RatelimitBucket
from ..errors import Ratelimited, Banned, FailedAuth
from ..common import check_bans, get_ip_addr
from ..common.auth import token_check

log = logging.getLogger(__name__)
bp = Blueprint("ratelimit", __name__)


# force ip based ratelimiting on those rules.
FORCE_IP = (
    "auth.login_handler",
    "auth.apikey_handler",
    "auth.revoke_handler",
    "misc.hello",
)


@dataclass
class RatelimitContext:
    bucket: Optional[RatelimitBucket] = None
    retry_after: Optional[float] = None
    bucket_global: bool = False


def _check_bucket(bucket: RatelimitBucket):
    """Check the ratelimit bucket."""
    retry_after = bucket.update_rate_limit()
    ctx = request.ratelimit_context
    ctx.bucket = bucket
    if bucket.retries > app.econfig.RL_THRESHOLD:
        raise Banned("Reached retry limit on ratelimiting.")

    if retry_after:
        ctx.retry_after = retry_after
        raise Ratelimited("You are being rate limited.", retry_after)


async def _handle_ratelimit(
    ratelimit: Optional[RatelimitManager], is_global: bool = False
):
    try:
        _username, user_id = request._user
    except AttributeError:
        user_id = get_ip_addr()
        # check_bans for user ids is already called when we're checking
        # the token.
        await check_bans(None)

    if is_global:
        ctx = request.ratelimit_context
        ctx.bucket_global = True
        ratelimit = app.ratelimits["*"]

    if ratelimit is None:
        return

    bucket = ratelimit.get_bucket(user_id)
    _check_bucket(bucket)


@bp.before_app_request
async def ratelimit_handler():
    if request.method == "OPTIONS":
        return

    rule = request.url_rule

    # for the given request, we create a context so we can generate
    # the x- ratelimit headers by the time we're making our response

    # _handle_global and _handle_specific fill the context.
    request.ratelimit_context = RatelimitContext()

    # NOTE IIRC rule is None when the client is trying to access
    # static resources on the app, so right now i fall it back to
    # being the global ratelimit.
    if rule is None:
        await _handle_ratelimit(None, is_global=True)
        return

    # rule.endpoint is composed of '<blueprint>.<function>'
    # and so we can use that to make routes with different
    # methods have different ratelimits
    rule_path = rule.endpoint

    try:
        user_id = await token_check()
        username = await app.storage.get_username(user_id)
        request._user = (username, user_id)
    except FailedAuth:
        pass

    if rule_path in app.ratelimits:
        await _handle_ratelimit(app.ratelimits[rule_path])
    else:
        await _handle_ratelimit(None, is_global=True)


@bp.after_app_request
async def rl_header_set(response):
    """Set ratelimit headers when possible!"""
    try:
        ctx = request.ratelimit_context
    except AttributeError:
        return response

    bucket = ctx.bucket
    if bucket is None:
        return response

    response.headers["X-RateLimit-Limit"] = str(bucket.requests)
    response.headers["X-RateLimit-Remaining"] = str(bucket._tokens)
    response.headers["X-RateLimit-Reset"] = str(bucket._window + bucket.second)

    return response


def setup_ratelimits():
    rtls = app.econfig.RATELIMITS
    app.ratelimits = {}

    for endpoint, ratelimit in rtls.items():
        log.debug("Ratelimit for '%s' set to %r", endpoint, ratelimit)
        app.ratelimits[endpoint] = RatelimitManager(*ratelimit)

    # if a global ratelimit isn't provided, inject a default one.
    if "*" not in app.ratelimits:
        log.debug("Ratelimit for '*' set to default")
        app.ratelimits["*"] = RatelimitManager(15, 5)
