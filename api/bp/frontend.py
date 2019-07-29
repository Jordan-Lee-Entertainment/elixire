# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, send_file, current_app as app

bp = Blueprint("frontend", __name__)


async def maybe_send(path):
    if not app.econfig.ENABLE_FRONTEND:
        return "frontend is not enabled", 405

    return await send_file(path)


@bp.route("/")
async def main_frontend_index():
    return await maybe_send("./frontend/output/index.html")


@bp.route("/<path:path>")
async def main_frontend(path: str):
    return await maybe_send(f"./frontend/output/{path}")


@bp.route("/admin")
async def main_admin_index():
    return await maybe_send("./admin-panel/build/index.html")


@bp.route("/admin/<path:path>")
async def main_admin(path: str):
    return await maybe_send(f"./admin-panel/build/{path}")
