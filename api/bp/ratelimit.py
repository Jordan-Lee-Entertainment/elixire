# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - ratelimit blueprint
"""
from sanic import Blueprint
from ..ratelimit import RatelimitManager
from ..errors import Ratelimited, Banned
from ..common import check_bans, get_ip_addr
from ..common.auth import token_check, get_token

bp = Blueprint('ratelimit')


FORCE_IP = (
    '/api/login',
    '/api/apikey',
    '/api/revoke',
    '/api/hello',
)


def check_rtl(request, bucket):
    """Check the ratelimit bucket."""
    retry_after = bucket.update_rate_limit()
    if bucket.retries > request.app.econfig.RL_THRESHOLD:
        raise Banned('Reached retry limit on ratelimiting.')

    if retry_after:
        raise Ratelimited('You are being ratelimited.', retry_after)


async def finish_ratelimit(request, best_rtl, bucket_key,
                           do_ban_checking: bool = False):
    """Finish the ratelimiting operation.
        - getting the bucket, setting it as _ratelimit_bucket
        - checking ban info (only when required)
        - checking if the bucket is exploded
            (and giving a 429 when that happens)
    """
    bucket = best_rtl.get_bucket(bucket_key)
    request['_ratelimit_bucket'] = bucket

    if do_ban_checking:
        # the only case where ratelimiting code needs
        # to call check_bans is when we are on an ip-only context.

        # if we are on a user context, we already called token_check,
        # and token_check, by default, calls check_bans

        # calling check_bans from here without any flags up
        # would be a waste of redis calls.
        await check_bans(request, None)

    return check_rtl(request, bucket)


@bp.middleware('request')
async def ratelimit_handler(request):
    """Ratelimit handler."""
    # ignore any OPTIONS
    if request.method == 'OPTIONS':
        return

    app = request.app

    # list of preferred ratelimit buckets
    preferred = []

    try:
        token = get_token(request)
    except KeyError:
        token = False

    token = False if any(r in request.path for r in FORCE_IP) else token

    preferred_scope = 'token' if token else 'ip'
    request['_ratelimit_scope'] = preferred_scope

    # search through all defined ratelimits in configuration file,
    #  find the *preferred ones*.

    # e.g if a request has Authorization header, we only search for
    #  ratelimit configurations that work on the 'token' scope.
    # if a request doesn't have Authorization, we use the 'ip' scope.
    for scope, ratelimit in app.ratelimits.items():
        try:
            req_scope, path_scope = scope
        except ValueError:
            req_scope, path_scope = 'token', scope

        if req_scope == preferred_scope and \
                request.path.startswith(path_scope):
            preferred.append(ratelimit)

    # find the best ratelimiter

    # we use the longest scope of the rateimiter to find the best one:
    #  if the scopes were /, /api/hello and /api, the /api/hello scope
    #  would win.
    def _scope_length(rtl):
        try:
            _, path_scope = rtl.scope
            return len(path_scope)
        except ValueError:
            return len(rtl.scope)

    sorted_rtl = sorted(preferred,
                        key=_scope_length,
                        reverse=True)
    if sorted_rtl:
        best_rtl = sorted_rtl[0]
    else:
        return

    rtl_path_scope = best_rtl.scope
    if isinstance(rtl_path_scope, tuple):
        request['_ratelimit_path'] = rtl_path_scope[1]
    else:
        request['_ratelimit_path'] = rtl_path_scope

    # from the best ratelimiter, acquire the bucket
    # (which is based on IP or user ID)
    if preferred_scope == 'ip':
        ip_address = get_ip_addr(request)
        return await finish_ratelimit(
            request, best_rtl, ip_address, True)

    # user-based ratelimiting from now on
    user_id = await token_check(request)
    username = await app.storage.get_username(user_id)

    request['ctx'] = (username, user_id)
    return await finish_ratelimit(
        request, best_rtl, username)


@bp.middleware('response')
async def rl_header_set(request, resp):
    """Set ratelimit headers when possible!"""
    if request.method == 'OPTIONS':
        return

    try:
        bucket = request['_ratelimit_bucket']
    except KeyError:
        # no ratelimit bucket was made for this request
        return

    try:
        resp.headers['X-Ratelimit-Scope'] = request['_ratelimit_scope']
    except KeyError:
        pass

    try:
        resp.headers['X-Ratelimit-Path'] = request['_ratelimit_path']
    except KeyError:
        pass

    if bucket:
        resp.headers['X-RateLimit-Limit'] = bucket.requests
        resp.headers['X-RateLimit-Remaining'] = bucket._tokens
        resp.headers['X-RateLimit-Reset'] = bucket._window + bucket.second


@bp.listener('before_server_start')
async def start_ratelimiters(app, _loop):
    rtls = app.econfig.RATELIMITS
    app.ratelimits = {}

    for scope, ratelimit in rtls.items():
        app.ratelimits[scope] = RatelimitManager(scope, ratelimit)
