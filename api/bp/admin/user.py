# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from math import ceil

from sanic import Blueprint, response

from api.decorators import admin_route
from api.errors import NotFound, BadInput
from api.schema import validate, ADMIN_MODIFY_USER

from api.common.email import (
    fmt_email, send_user_email, activate_email_send,
    uid_from_email, clean_etoken
)

from api.bp.profile import get_limits, delete_user

from api.bp.admin.audit_log_actions.user import UserEditAction, UserDeleteAction

log = logging.getLogger(__name__)
bp = Blueprint(__name__)


@bp.get('/api/admin/users/<user_id:int>')
@admin_route
async def get_user_handler(request, admin_id, user_id: int):
    """Get a user's details in the service."""
    udata = await request.app.db.fetchrow("""
    SELECT user_id, username, active, admin, domain, subdomain,
      consented, email, paranoid
    FROM users
    WHERE user_id=$1
    """, user_id)

    if not udata:
        raise NotFound('User not found')

    dudata = dict(udata)
    dudata['user_id'] = str(dudata['user_id'])
    dudata['limits'] = await get_limits(request.app.db, user_id)

    return response.json(dudata)


async def notify_activate(app, user_id: int):
    """Inform user that they got an account."""
    if not app.econfig.NOTIFY_ACTIVATION_EMAILS:
        return

    log.info(f'Sending activation email to {user_id}')

    body = fmt_email(app, """This is an automated email from {inst_name}
about your account request.

Your account has been activated and you can now log in
at {main_url}/login.html.

Welcome to {inst_name}!

Send an email to {support} if any questions arise.
Do not reply to this automated email.

- {inst_name}, {main_url}
    """)

    subject = fmt_email(app, "{inst_name} - Your account is now active")
    resp_tup, user_email = await send_user_email(
        app, user_id, subject, body)

    resp, _ = resp_tup

    if resp.status == 200:
        log.info(f'Sent email to {user_id} {user_email}')
    else:
        log.error(f'Failed to send email to {user_id} {user_email}')


@bp.post('/api/admin/activate/<user_id:int>')
@admin_route
async def activate_user(request, admin_id, user_id: int):
    """Activate one user, given its ID."""
    async with UserEditAction(request, user_id):
        result = await request.app.db.execute("""
        UPDATE users
        SET active = true
        WHERE user_id = $1
        """, user_id)

        if result == "UPDATE 0":
            raise BadInput('Provided user ID does not reference any user.')

    await request.app.storage.invalidate(user_id, 'active')
    await notify_activate(request.app, user_id)

    return response.json({
        'success': True,
        'result': result,
    })


@bp.post('/api/admin/activate_email/<user_id:int>')
@admin_route
async def activation_email(request, admin_id, user_id):
    """Send an email to the user so they become able
    to activate their account manually."""
    active = await request.app.db.fetchval("""
    SELECT active
    FROM users
    WHERE user_id = $1
    """, user_id)

    if active is None:
        raise BadInput('Provided user_id does not reference any user')

    if active:
        raise BadInput('User is already active')

    # there was an invalidate() call which is unecessary
    # because its already invalidated on activate_user_from_email

    resp_tup, _email = await activate_email_send(request.app, user_id)
    resp, _ = resp_tup

    return response.json({
        'success': resp.status == 200,
    })


@bp.get('/api/activate_email')
async def activate_user_from_email(request):
    """Called when a user clicks the activation URL in their email."""
    try:
        email_token = str(request.raw_args['key'])
    except (KeyError, TypeError):
        raise BadInput('no key provided')

    app = request.app
    user_id = await uid_from_email(app, email_token, 'email_activation_tokens')

    res = await request.app.db.execute("""
    UPDATE users
    SET active = true
    WHERE user_id = $1
    """, user_id)

    await request.app.storage.invalidate(user_id, 'active')
    await clean_etoken(app, email_token, 'email_activation_tokens')
    log.info(f'Activated user id {user_id}')

    return response.json({
        'success': res == 'UPDATE 1'
    })


@bp.post('/api/admin/deactivate/<user_id:int>')
@admin_route
async def deactivate_user(request, admin_id: int, user_id: int):
    """Deactivate one user, given its ID."""
    async with UserEditAction(request, user_id):
        result = await request.app.db.execute("""
        UPDATE users
        SET active = false
        WHERE user_id = $1
        """, user_id)

        if result == "UPDATE 0":
            raise BadInput('Provided user ID does not reference any user.')

    await request.app.storage.invalidate(user_id, 'active')

    return response.json({
        'success': True,
        'result': result
    })


def _extract_active(args: dict) -> tuple:
    """Extract the wanted active-ness values for our search query."""
    active = args.get('active')

    # if active is None, we return True, False, that means the query
    # will search users that are either active OR inactive. by returning
    # the same value on the elements of the tuple, we can do a whole search
    # on active/inactive users separately, instead of both
    if active is None:
        return True, False

    is_active = active.lower() != 'false'
    return is_active, is_active


@bp.get('/api/admin/users/search')
@admin_route
async def users_search(request, admin_id):
    """New, revamped search endpoint."""
    args = request.raw_args
    query = request.raw_args.get('query')
    page = int(args.get('page', 0))
    per_page = int(args.get('per_page', 20))

    if page < 0:
        raise BadInput('Invalid page number')

    if per_page < 1:
        raise BadInput('Invalid per_page number')

    active, active_reverse = _extract_active(args)

    users = await request.app.db.fetch(f"""
    SELECT user_id, username, active, admin, consented,
           COUNT(*) OVER() as total_count
    FROM users
    WHERE active = $1 OR active = $2
    AND (
            $4 = ''
            OR (username LIKE '%'||$4||'%' OR user_id::text LIKE '%'||$4||'%')
        )
    ORDER BY user_id ASC
    LIMIT {per_page}
    OFFSET ($3 * {per_page})
    """, active, active_reverse, page, query or '')

    def map_user(record):
        row = dict(record)
        row['user_id'] = str(row['user_id'])
        del row['total_count']
        return row

    results = map(map_user, users)
    total_count = 0 if not users else users[0]['total_count']

    return response.json({
        'results': results,
        'pagination': {
            'total': ceil(total_count / per_page),
            'current': page
        }
    })


# === DEPRECATED ===
#  read https://gitlab.com/elixire/elixire/issues/61#note_91039503
# These routes are here to maintain compatibility with some of our
# utility software (admin panels)


@bp.get('/api/admin/listusers/<page:int>')
@admin_route
async def list_users_handler(request, admin_id, page: int):
    """List users in the service"""
    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain,
      subdomain, email, paranoid, consented
    FROM users
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($1 * 20)
    """, page)

    def _cnv(row):
        drow = dict(row)
        drow['user_id'] = str(row['user_id'])
        return drow

    return response.json(list(map(_cnv, data)))


@bp.get('/api/admin/list_inactive/<page:int>')
@admin_route
async def inactive_users_handler(request, admin_id, page: int):
    data = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, domain, subdomain,
      email, paranoid, consented
    FROM users
    WHERE active=false
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($1 * 20)
    """, page)

    def _cnv(row):
        drow = dict(row)
        drow['user_id'] = str(row['user_id'])
        return drow

    return response.json(list(map(_cnv, data)))


@bp.post('/api/admin/search/user/<page:int>')
async def search_user(request, user_id: int, page: int):
    """Search a user by pattern matching the username."""
    try:
        pattern = str(request.json['search_term'])
    except (KeyError, TypeError, ValueError):
        raise BadInput('Invalid search_term')

    if not pattern:
        raise BadInput('Insert a pattern.')

    pattern = f'%{pattern}%'

    rows = await request.app.db.fetch("""
    SELECT user_id, username, active, admin, consented
    FROM users
    WHERE username LIKE $1 OR user_id::text LIKE $1
    ORDER BY user_id ASC
    LIMIT 20
    OFFSET ($2 * 20)
    """, pattern, page)

    res = []

    for row in rows:
        drow = dict(row)
        drow['user_id'] = str(drow['user_id'])
        res.append(drow)

    return response.json(res)


# === END DEPRECATED ===


async def _pu_check(db, db_name,
                    user_id, payload, updated_fields, field, col=None):
    """Checks if the given field exists on payload.

    If it does exist, it will update the given database and column
    with the given value on the payload.

    Parameters
    ----------
    db
        Database connection.
    db_name: str
        Database to update on.
    user_id: int
        User id we are updating the row on.
    payload: dict
        Request's payload.
    updated_fields: list
        The list of currently updated fields, to give
        as a response on the request handler.
    field: str
        The field we want to search on the payload
        and add to updated_fields
    col: str, optional
        The column to update, in the case col != field.
    """

    # Yes, this function takes a lot of arguments,
    # read the comment block on modify_user to know why
    if not col:
        col = field

    # check if field exists
    val = payload.get(field)
    if val is not None:

        # if it does exist, update on database
        await db.execute(f"""
        UPDATE {db_name}
        SET {col} = $1
        WHERE user_id = $2
        """, val, user_id)

        updated_fields.append(field)


@bp.patch('/api/admin/user/<user_id:int>')
@admin_route
async def modify_user(request, admin_id, user_id):
    """Modify a user's information."""
    payload = validate(request.json, ADMIN_MODIFY_USER)

    updated = []

    db = request.app.db

    # _pu_check serves as a template for the following code structure:
    #   X = payload.get(field)
    #   if X is not None:
    #     update db with field
    #     updated.append(field)

    async with UserEditAction(request, user_id):
        await _pu_check(db, 'users', user_id, payload, updated, 'email')
        await _pu_check(db, 'limits', user_id, payload, updated,
                        'upload_limit', 'blimit')
        await _pu_check(db, 'limits', user_id, payload, updated,
                        'shorten_limit', 'shlimit')

    return response.json(updated)


@bp.delete('/api/admin/user/<user_id:int>')
@admin_route
async def del_user(request, admin_id, user_id):
    """Delete a single user.

    File deletion happens in the background.
    """
    active = await request.app.db.fetchval("""
    SELECT active
    FROM users
    WHERE user_id = $1
    """, user_id)

    if active is None:
        raise BadInput('user not found')

    async with UserDeleteAction(request, user_id):
        await delete_user(request.app, user_id, True)

    return response.json({
        'success': True
    })
