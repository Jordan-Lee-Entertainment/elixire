# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from sanic import Blueprint, response
from sanic.router import RouteExists

bp = Blueprint('frontend')


async def maybe_send(app, path):
    if app.econfig.ENABLE_FRONTEND:
        return await response.file(path)

    return response.text('frontend is not enabled')


@bp.get('/')
async def main_frontend_index(request):
    return await maybe_send(request.app, './frontend/output/index.html')


async def main_frontend(request, **_paths):
    return await maybe_send(request.app, f'./frontend/output/{request.path}')


@bp.get('/admin')
async def main_admin_index(request):
    return await maybe_send(request.app, './admin-panel/build/index.html')


async def main_admin(request, **paths):
    path = '/'.join([p for p in paths.values()])
    return await maybe_send(request.app, f'./admin-panel/build/{path}')


@bp.listener('before_server_start')
async def add_frontend_routes(app, _loop):
    for i in range(1, 5):
        components = [f'/<path{n}>' for n in range(i)]
        path = ''.join(components)

        try:
            app.add_route(main_frontend, path, methods=['GET'])
        except RouteExists:
            pass

        try:
            app.add_route(main_admin, f'/admin{path}', methods=['GET'])
        except RouteExists:
            pass
