import pathlib

from sanic import Blueprint
from sanic import response

from ..common_auth import token_check, check_admin, check_domain
from ..errors import NotFound, QuotaExploded
from ..common import gen_filename
from ..snowflake import get_snowflake

bp = Blueprint('shorten')


@bp.get('/s/<filename>')
async def shorten_serve_handler(request, filename):
    """Handles serving of shortened links."""
    domain = await check_domain(request, request.host)

    storage = request.app.storage
    url_toredir = await storage.get_urlredir(filename, domain['domain_id'])

    if not url_toredir:
        raise NotFound('No shortened links found with this name '
                       'on this domain.')

    return response.redirect(url_toredir)


@bp.post('/api/shorten')
async def shorten_handler(request):
    """Handles addition of shortened links."""

    user_id = await token_check(request)
    url_toredir = str(request.json['url'])

    # Check if admin is set in get values, if not, do checks
    # If it is set, and the admin value is truthy, do not do checks
    do_checks = not ('admin' in request.args and request.args['admin'])

    # Let's actually check if the user is an admin
    # and raise an error if they're not an admin
    if not do_checks:
        await check_admin(request, user_id, True)

    # Skip checks for admins
    if do_checks:
        shortens_used = await request.app.db.fetch("""
        SELECT shorten_id
        FROM shortens
        WHERE uploader = $1
        AND shorten_id > time_snowflake(now() - interval '7 days')
        """, user_id)

        shortens_used = len(shortens_used)

        shorten_limit = await request.app.db.fetchval("""
        SELECT shlimit
        FROM limits
        WHERE user_id = $1
        """, user_id)

        if shortens_used and shortens_used > shorten_limit:
            raise QuotaExploded('You already blew your weekly'
                                f' limit of {shorten_limit} shortens')

        if shortens_used and shortens_used + 1 > shorten_limit:
            raise QuotaExploded('This shorten blows the weekly limit of'
                                f' {shorten_limit} shortens')

    redir_rname = await gen_filename(request)
    redir_id = get_snowflake()

    # get domain ID from user and return it
    domain_id = await request.app.db.fetchval("""
    SELECT domain
    FROM users
    WHERE user_id = $1
    """, user_id)

    await request.app.db.execute("""
    INSERT INTO shortens (shorten_id, filename,
        uploader, redirto, domain)
    VALUES ($1, $2, $3, $4, $5)
    """, redir_id, redir_rname, user_id, url_toredir, domain_id)

    domain = await request.app.db.fetchval("""
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    # appended to generated filename
    dpath = pathlib.Path(domain)
    fpath = dpath / 's' / f'{redir_rname}'

    return response.json({
        'url': f'https://{str(fpath)}'
    })
