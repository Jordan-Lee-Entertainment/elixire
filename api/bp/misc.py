"""
elixire - misc routes
"""
from sanic import Blueprint, response
from ..common import VERSION

bp = Blueprint('misc')


@bp.get('/api/hello')
async def hello_route(request):
    """Give basic information about the instance. Name and backend version."""
    return response.json({
        'name': request.app.econfig.INSTANCE_NAME,
        'version': VERSION,
    })


@bp.get('/api/hewwo')
async def h_hewwo(request):
    """owo"""
    return response.json({
        'name': request.app.econfig.INSTANCE_NAME.replace('r', 'w'),
        'version': VERSION.replace('0', '0w0'),
    })


@bp.get('/api/features')
async def fetch_features(request):
    """Fetch instance features.

    So that the frontend can e.g disable the
    register button when the instance's registration enabled
    flag is set to false.
    """
    cfg = request.app.econfig

    return response.json({
        'uploads': cfg.UPLOADS_ENABLED,
        'shortens': cfg.SHORTENS_ENABLED,
        'registrations': cfg.REGISTRATIONS_ENABLED,
        'pfupdate': cfg.PATCH_API_PROFILE_ENABLED,
    })
