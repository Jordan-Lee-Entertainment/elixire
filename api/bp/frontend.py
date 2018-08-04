from sanic import Blueprint, response

bp = Blueprint('frontend')


def maybe_send(app, path):
    if app.econfig.ENABLE_FRONTEND:
        return response.file(path)

    return response.text('frontend is not enabled')


@bp.get('/')
async def main_frontend_index(request):
    return maybe_send(request.app, './frontend/output/index.html')


@bp.get('/<path>')
async def main_frontend(request, path):
    return maybe_send(request.app, f'./frontend/output/{request.path}')


@bp.get('/admin')
async def main_admin_index(request):
    return maybe_send(request.app, './admin-panel/build/index.html')


@bp.get('/admin/<path>')
async def main_admin(request, path):
    return maybe_send(request.app, f'./admin-panel/build/{request.path}')
