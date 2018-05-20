import logging

from sanic import Blueprint, response

from ..common_auth import token_check, check_admin
from ..errors import NotFound, BadInput

log = logging.getLogger(__name__)
bp = Blueprint('datadump')


async def dump_worker(app):
    log.info('dump worker start')


@bp.listener('after_server_start')
async def start_dump_worker_ss(app, loop):
    loop.create_task(dump_worker(app))


@bp.post('/api/dump/request')
async def request_data_dump(request):
    """Request a data dump to be scheduled
    at the earliest convenience of the system."""
    pass


@bp.get('/api/dump/status')
async def data_dump_user_status(request):
    """Give information about the current dump for the user,
    if one exists."""
    pass


@bp.get('/api/dump/global_status')
async def data_dump_global_status(request):
    """Only for admins: all stuff related to data dump state."""
    pass
