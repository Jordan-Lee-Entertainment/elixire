# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

# This blueprint contains routes for the sole purpose of being humorous.

import datetime
import logging
import random

from sanic import Blueprint
from sanic import response

bp = Blueprint('wpadmin')
log = logging.getLogger(__name__)

WORLD_POWER_DEADLINE = datetime.date(2023, 7, 24)

# Inspired by:
# https://gist.github.com/NickCraver/c9458f2e007e9df2bdf03f8a02af1d13

memes = [
    "https://www.youtube.com/watch?v=rRbY3TMUcgQ",
    "https://www.youtube.com/watch?v=o0Wvn-9BXVc",
    "https://www.youtube.com/watch?v=b2F-DItXtZs",
    "https://www.youtube.com/watch?v=5GpOfwbFRcs",
    "https://www.youtube.com/watch?v=pCOCKS5AJI8",
    "https://www.youtube.com/watch?v=bzkRVzciAZg"
]


@bp.get('ajaxproxy/proxy.php')
@bp.get('bitrix/admin/index.php')
@bp.get('magmi/web/magmi.php')
@bp.get('wp-admin/admin-ajax.php')
@bp.get('wp-admin/includes/themes.php')
@bp.get('wp-admin/options-link.php')
@bp.get('wp-admin/post-new.php')
@bp.get('wp-login.php')
@bp.get('xmlrpc.php')
async def wpadmin(request):
    """Redirect bots to memes."""

    url = random.choice(memes)

    return response.redirect(url)


@bp.get('/api/science')
async def science_route(request):
    """*insert b4nzyblob*"""
    return response.text("Hewoo! We'we nyot discowd we don't spy on nyou :3")


@bp.get('/api/boron')
async def ipek_yolu(request):
    """calculates days until 100th year anniversary of treaty of lausanne"""
    today = datetime.date.today()
    days_to_wp = (WORLD_POWER_DEADLINE - today).days
    is_world_power = (days_to_wp <= 0)

    return response.json({
        'world_power': is_world_power,
        'days_until_world_power': days_to_wp
    })

