# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path
from quart import Blueprint, send_file, current_app as app

bp = Blueprint("frontend", __name__)


async def maybe_send(file_path: str):
    # TODO make better detection for hellish paths (check parenting against
    # the preffered frontend folder)
    if ".." in file_path:
        return "no", 404

    if app.cfg.ENABLE_FRONTEND:
        return await send_file(file_path)

    return "frontend is not enabled"


@bp.route("/<path:path>")
async def frontend_path(path):
    """Map requests from / to /static."""
    static_path = Path.cwd() / Path("frontend/output") / path
    return await maybe_send(str(static_path))


@bp.get("/")
async def frontend_index():
    """Handler for the index page."""
    return await maybe_send("./frontend/output/index.html")


@bp.get("/admin/<path:path>")
async def admin_path(path):
    static_path = Path.cwd() / Path("admin-panel/build") / path
    return await maybe_send(str(static_path))


@bp.get("/admin")
async def admin_index():
    return await maybe_send("./admin-panel/build/index.html")


@bp.get("/robots.txt")
async def robots_txt():
    return await send_file("./static/robots.txt")


@bp.get("/humans.txt")
async def humans_txt():
    return await send_file("./static/humans.txt")
