# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire - misc routes
"""
import datetime
from quart import Blueprint, jsonify, current_app as app
from ..version import VERSION, API_VERSION

bp = Blueprint("misc", __name__)


def _owo(string: str) -> str:
    return string.replace("0", "0w0").replace("r", "w")


@bp.get("/hello")
async def hello_route():
    """Give basic information about the instance."""
    cfg = app.cfg

    return jsonify(
        {
            "name": cfg.INSTANCE_NAME,
            "version": VERSION,
            "api": API_VERSION,
            "invite": cfg.MAIN_INVITE,
            "support_email": cfg.SUPPORT_EMAIL,
            "ban_period": cfg.BAN_PERIOD,
            "ip_ban_period": cfg.IP_BAN_PERIOD,
            "rl_threshold": cfg.RL_THRESHOLD,
            "accepted_mimes": cfg.ACCEPTED_MIMES,
        }
    )


@bp.get("/hewwo")
async def h_hewwo():
    """owo"""
    return jsonify(
        {
            "name": _owo(app.cfg.INSTANCE_NAME),
            "version": _owo(VERSION),
            "api": _owo(API_VERSION),
        }
    )


@bp.get("/science")
async def science_route():
    """*insert b4nzyblob*"""
    return "Hewoo! We'we nyot discowd we don't spy on nyou :3"


@bp.get("/boron")
async def ipek_yolu():
    """calculates days until 100th year anniversary of treaty of lausanne"""
    world_power_deadline = datetime.date(2023, 7, 24)
    days_to_wp = (world_power_deadline - datetime.date.today()).days
    is_world_power = days_to_wp <= 0
    return jsonify(
        {"world_power": is_world_power, "days_until_world_power": days_to_wp}
    )


@bp.get("/features")
async def fetch_features():
    """Fetch instance features.

    So that the frontend can e.g disable the
    register button when the instance's registration enabled
    flag is set to false.
    """
    cfg = app.cfg

    return jsonify(
        {
            "uploads": cfg.UPLOADS_ENABLED,
            "shortens": cfg.SHORTENS_ENABLED,
            "registrations": cfg.REGISTRATIONS_ENABLED,
            "pfupdate": cfg.PATCH_API_PROFILE_ENABLED,
        }
    )
