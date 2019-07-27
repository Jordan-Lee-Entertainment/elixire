# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

# This blueprint contains routes for the sole purpose of being humorous.

import datetime
import random

from quart import Blueprint, redirect, jsonify

bp = Blueprint("wpadmin", __name__)

WORLD_POWER_DEADLINE = datetime.date(2023, 7, 24)

# Inspired by:
# https://gist.github.com/NickCraver/c9458f2e007e9df2bdf03f8a02af1d13

memes = [
    "https://www.youtube.com/watch?v=rRbY3TMUcgQ",
    "https://www.youtube.com/watch?v=o0Wvn-9BXVc",
    "https://www.youtube.com/watch?v=b2F-DItXtZs",
    "https://www.youtube.com/watch?v=5GpOfwbFRcs",
    "https://www.youtube.com/watch?v=pCOCKS5AJI8",
    "https://www.youtube.com/watch?v=bzkRVzciAZg",
]


@bp.route("/ajaxproxy/proxy.php")
@bp.route("/bitrix/admin/index.php")
@bp.route("/magmi/web/magmi.php")
@bp.route("/wp-admin/admin-ajax.php")
@bp.route("/wp-admin/includes/themes.php")
@bp.route("/wp-admin/options-link.php")
@bp.route("/wp-admin/post-new.php")
@bp.route("/wp-login.php")
@bp.route("/xmlrpc.php")
async def wpadmin():
    """Redirect bots to memes."""
    url = random.choice(memes)
    return redirect(url)


@bp.route("/api/science")
async def science_route():
    """*insert b4nzyblob*"""
    return "Hewoo! We'we nyot discowd we don't spy on nyou :3", 200


@bp.route("/api/boron")
async def ipek_yolu():
    """calculates days until 100th year anniversary of treaty of lausanne"""
    today = datetime.date.today()
    days_to_wp = (WORLD_POWER_DEADLINE - today).days
    is_world_power = days_to_wp <= 0

    return jsonify(
        {"world_power": is_world_power, "days_until_world_power": days_to_wp}
    )
