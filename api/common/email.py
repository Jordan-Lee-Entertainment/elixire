import secrets

import aiohttp

from ..errors import BadInput


async def gen_email_token(app, user_id, table: str, count: int = 0) -> str:
    """Generate a token for email usage.

    Calls the database to give an unique token.

    Parameters
    ----------
    app: sanic.App
        Application instance for database access.
    user_id: int
        User snowflake ID.
    table: str
        The table to be used for checking.

    Returns
    -------
    str
        The email token to be used.

    Raises
    ------
    BadInput
        When the funcion entered more than 10 retries,
        or there are more than 3 tokens issued in the span
        of a time window (defined by the table)
    """
    if count == 11:
        # it really shouldn't happen,
        # but we better be ready for it.
        raise BadInput('Failed to generate an email hash.')

    possible = secrets.token_hex(32)

    # check if hash already exists
    other_id = await app.db.fetchval(f"""
    SELECT user_id
    FROM {table}
    WHERE hash = $1 AND now() < expiral
    """, possible)

    if other_id:
        # retry with count + 1
        await gen_email_token(app, user_id, table, count + 1)

    # check if there are more than 3 issues hashes for the user.
    hashes = await app.db.fetchval(f"""
    SELECT COUNT(*)
    FROM {table}
    WHERE user_id = $1 AND now() < expiral
    """, user_id)

    if hashes > 3:
        raise BadInput('You already generated more than 3 tokens '
                       'in the time period.')

    return possible


async def send_email(app, user_email: str, subject: str, email_body: str):
    """Send an email to a user using the Mailgun API."""
    econfig = app.econfig
    mailgun_url = (f'https://api.mailgun.net/v3/{econfig.MAILGUN_DOMAIN}'
                   '/messages')

    _inst_name = econfig.INSTANCE_NAME

    auth = aiohttp.BasicAuth('api', econfig.MAILGUN_API_KEY)
    data = {
        'from': f'{_inst_name} <automated@{econfig.MAILGUN_DOMAIN}>',
        'to': [user_email],
        'subject': subject,
        'text': email_body,
    }

    async with app.session.post(mailgun_url,
                                auth=auth, data=data) as resp:
        return resp
