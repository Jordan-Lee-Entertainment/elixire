# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - misc routes
"""
import datetime
from sanic import Blueprint, response
from ..version import VERSION, API_VERSION

bp = Blueprint('misc')


def _owo(string: str) -> str:
    return string.replace('0', '0w0').replace('r', 'w')


def make_feature_list(cfg):
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
        'features': make_feature_list(cfg)
    })


@bp.get('/api/hewwo')
async def h_hewwo(request):
    """owo"""
    return response.json({
        'name': _owo(request.app.econfig.INSTANCE_NAME),
        'version': _owo(VERSION),
        'api': _owo(API_VERSION),
    })


@bp.get('/api/science')
async def science_route(request):
    """*insert b4nzyblob*"""
    return response.text("Hewoo! We'we nyot discowd we don't spy on nyou :3")


@bp.get('/api/boron')
async def ipek_yolu(request):
    """calculates days until 100th year anniversary of treaty of lausanne"""
    world_power_deadline = datetime.date(2023, 7, 24)
    days_to_wp = (world_power_deadline - datetime.date.today()).days
    is_world_power = (days_to_wp <= 0)
    return response.json({
        'world_power': is_world_power,
        'days_until_world_power': days_to_wp
    })


@bp.get('/api/features')
async def fetch_features(request):
    """Fetch instance features.

    So that the frontend can e.g disable the
    register button when the instance's registration enabled
    flag is set to false.
    """
    cfg = request.app.econfig

    return response.json({
        'uploads': cfg.UPLOADS_ENABLED,
        'shortens': cfg.SHORTENS_ENABLED,
        'registrations': cfg.REGISTRATIONS_ENABLED,
        'pfupdate': cfg.PATCH_API_PROFILE_ENABLED,
    })
