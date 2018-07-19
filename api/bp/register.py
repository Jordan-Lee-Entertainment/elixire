"""
elixi.re backend source code - register route
"""

import bcrypt
import asyncpg

from sanic import Blueprint, response

from ..snowflake import get_snowflake
from ..errors import BadInput, FeatureDisabled
from ..schema import validate, REGISTRATION_SCHEMA
from ..common.email import send_email, fmt_email
from ..common.webhook import register_webhook

bp = Blueprint('register')


async def send_register_email(app, email: str) -> bool:
    """Send an email about the signup."""
    _inst_name = app.econfig.INSTANCE_NAME

    email_body = fmt_email(app, """This is an automated email from {inst_name}
about your signup.

It has been successfully dispatched to the system so that admins can
activate the account. You will not be able to login until the account
is activated.

Accounts that aren't on the discord server won't be activated.
{main_invite}

Please do not re-register the account. It will just decrease your chances
of actually getting an account activated.

Reply to {support} if you have any questions.
Do not reply to this email specifially, it will not work.

 - {inst_name}, {main_url}
""")

    resp = await send_email(app, email,
                            f'{_inst_name} - signup confirmation',
                            email_body)

    return resp.status == 200


@bp.post('/api/register')
async def register_user(request):
    """Send an 'account registration request' to a certain
    discord webhook.

    Look into /api/admin/activate for registration acceptance.
    """
    if not request.app.econfig.REGISTRATIONS_ENABLED:
        raise FeatureDisabled('Registrations are currently disabled')

    payload = validate(request.json, REGISTRATION_SCHEMA)

    username = payload['username']
    password = payload['password']
    discord_user = payload['discord_user']
    email = payload['email']

    # borrowed from utils/adduser
    user_id = get_snowflake()

    _pwd = bytes(password, 'utf-8')
    hashed = bcrypt.hashpw(_pwd, bcrypt.gensalt(14))

    try:
        await request.app.db.execute("""
        INSERT INTO users (user_id, username, password_hash, email, active)
        VALUES ($1, $2, $3, $4, false)
        """, user_id, username, hashed.decode('utf-8'), email)
    except asyncpg.exceptions.UniqueViolationError:
        raise BadInput('Username or email already exist.')

    await request.app.db.execute("""
    INSERT INTO limits (user_id) VALUES ($1)
    """, user_id)

    # invalidate if anything happened before
    # just to make sure.
    await request.app.storage.raw_invalidate(f'uid:{username}')

    app = request.app

    succ = await send_register_email(app, email)
    succ_wb = await register_webhook(app, app.econfig.USER_REGISTER_WEBHOOK,
                                     user_id, username, discord_user, email)

    return response.json({
        'success': succ and succ_wb,
    })
