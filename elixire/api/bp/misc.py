# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, jsonify, current_app as app
from api.version import VERSION, API_VERSION

bp = Blueprint("misc", __name__)


def _make_feature_list(cfg):
    feature_mapping = {
        "uploads": cfg.UPLOADS_ENABLED,
        "shortens": cfg.SHORTENS_ENABLED,
        "registrations": cfg.REGISTRATIONS_ENABLED,
        "profile_editing": cfg.PATCH_API_PROFILE_ENABLED,
    }

    return [feature for feature in feature_mapping if feature_mapping[feature]]


@bp.route("/hello")
async def hello():
    """Give basic information about the instance."""
    cfg = app.econfig

    return jsonify(
        {
            "name": cfg.INSTANCE_NAME,
            "version": VERSION,
            "api_version": API_VERSION,
            "discord_invite": cfg.MAIN_INVITE,
            "support_email": cfg.SUPPORT_EMAIL,
            "accepted_mimes": cfg.ACCEPTED_MIMES,
            "ratelimits": {
                "ban_period": cfg.BAN_PERIOD,
                "ip_ban_period": cfg.IP_BAN_PERIOD,
                "threshold": cfg.RL_THRESHOLD,
            },
            "features": _make_feature_list(cfg),
            "approval_required": cfg.REQUIRE_ACCOUNT_APPROVALS,
        }
    )
