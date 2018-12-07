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

"""
elixire - misc routes
"""
import datetime
from sanic import Blueprint, response
from ..version import VERSION, API_VERSION

bp = Blueprint('misc')


def _owo(string: str) -> str:
    return string.replace('0', '0w0').replace('r', 'w')


@bp.get('/api/hello')
async def hello_route(request):
    """Give basic information about the instance."""
    return response.json({
        'name': request.app.econfig.INSTANCE_NAME,
        'version': VERSION,
        'api': API_VERSION,
        'support_email': request.app.econfig.SUPPORT_EMAIL,
        'ban_period': request.app.econfig.BAN_PERIOD,
        'ip_ban_period': request.app.econfig.IP_BAN_PERIOD,
        'rl_threshold': request.app.econfig.RL_THRESHOLD,
        'accepted_mimes': request.app.econfig.ACCEPTED_MIMES,
    })


@bp.get('/api/hewwo')
async def h_hewwo(request):
    """owo"""
    return response.json({
        'name': _owo(request.app.econfig.INSTANCE_NAME),
        'version': _owo(VERSION),
        'api': _owo(API_VERSION),
    })


@bp.get('/api/science')
async def science_route(request):
    """*insert b4nzyblob*"""
    return response.text("Hewoo! We'we nyot discowd we don't spy on nyou :3")


@bp.get('/api/boron')
async def ipek_yolu(request):
    """calculates days until 100th year anniversary of treaty of lausanne"""
    world_power_deadline = datetime.date(2023, 7, 24)
    days_to_wp = (world_power_deadline - datetime.date.today()).days
    is_world_power = (days_to_wp <= 0)
    return response.json({
        'world_power': is_world_power,
        'days_until_world_power': days_to_wp
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
