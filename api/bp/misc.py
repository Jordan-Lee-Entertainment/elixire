# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, jsonify, current_app as app
from api.version import VERSION, API_VERSION

bp = Blueprint("misc", __name__)


def _make_feature_list(cfg):
    res = []

    if cfg.UPLOADS_ENABLED:
        res.append("uploads")
    elif cfg.SHORTENS_ENABLED:
        res.append("shortens")
    elif cfg.REGISTRATIONS_ENABLED:
        res.append("registrations")
    elif cfg.PATCH_API_PROFILE_ENABLED:
        res.append("pfupdate")

    return res


@bp.route("/hello")
async def hello():
    """Give basic information about the instance."""
    cfg = app.econfig

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
            "features": _make_feature_list(cfg),
        }
    )
