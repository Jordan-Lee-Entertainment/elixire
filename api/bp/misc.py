# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - misc routes
"""
import datetime
from sanic import Blueprint, response
from ..version import VERSION, API_VERSION
import urllib.parse

bp = Blueprint('misc')


def _owo(string: str) -> str:
    return string.replace('0', '0w0').replace('r', 'w')

@bp.middleware('request')
async def bodyparser(request):
    """Make body available at request.body"""
    if request.body:
        # This _probably_ won't become an issue but no sense in tempting fate
        try:
            curly = bytes('{', request.headers.get('content-encoding', 'utf8'))
        except(LookupError):
            curly = bytes('{', 'utf8')

        if request.headers.get('content-type', 'application/json').startswith('application/x-www-form-urlencoded'):
            form = request.form
            # Cerberus doesn't like the old dict
            new_form = dict()
            for key in form.keys():
                new_form[key] = str(urllib.parse.unquote(form[key][0]))
            request.body = new_form
        elif request.headers.get('content-type', '').startswith('application/json') or (request.headers.get('content-type', None) != None and request.body.startswith(curly)):
            # Shaky, but it should be alright since we
            # need to support people who for whatever reason can't set it or something
            request.body = request.json
    return

@bp.get('/api/hello')
async def hello_route(request):
    """Give basic information about the instance."""
    return response.json({
        'name': request.app.econfig.INSTANCE_NAME,
        'version': VERSION,
        'api': API_VERSION,
        'support_email': request.app.econfig.SUPPORT_EMAIL,
        'ban_period': request.app.econfig.BAN_PERIOD,
        'ip_ban_period': request.app.econfig.IP_BAN_PERIOD,
        'rl_threshold': request.app.econfig.RL_THRESHOLD,
        'accepted_mimes': request.app.econfig.ACCEPTED_MIMES,
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
