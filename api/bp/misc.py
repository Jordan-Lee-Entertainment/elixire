# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import datetime

from sanic import Blueprint, response
from api.version import VERSION, API_VERSION

bp = Blueprint('misc')


def _make_feature_list(cfg):
    res = []

    if cfg.UPLOADS_ENABLED:
        res.append('uploads')
    elif cfg.SHORTENS_ENABLED:
        res.append('shortens')
    elif cfg.REGISTRATIONS_ENABLED:
        res.append('registrations')
    elif cfg.PATCH_API_PROFILE_ENABLED:
        res.append('pfupdate')

    return res


@bp.get('/api/hello')
async def hello_route(request):
    """Give basic information about the instance."""
    cfg = request.app.econfig

    return response.json({
        'name': cfg.INSTANCE_NAME,
        'version': VERSION,
        'api': API_VERSION,
        'support_email': cfg.SUPPORT_EMAIL,
        'ban_period': cfg.BAN_PERIOD,
        'ip_ban_period': cfg.IP_BAN_PERIOD,
        'rl_threshold': cfg.RL_THRESHOLD,
        'accepted_mimes': cfg.ACCEPTED_MIMES,
        'features': _make_feature_list(cfg)
    })
