"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

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
