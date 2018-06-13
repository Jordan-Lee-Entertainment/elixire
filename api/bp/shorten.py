import pathlib
import urllib.parse

from sanic import Blueprint
from sanic import response

from ..common.auth import token_check, check_admin
from ..errors import NotFound, QuotaExploded, BadInput, FeatureDisabled
from ..common import gen_filename, get_domain_info, transform_wildcard, \
    FileNameType
from ..snowflake import get_snowflake

bp = Blueprint('shorten')


@bp.get('/s/<filename>')
async def shorten_serve_handler(request, filename):
    """Handles serving of shortened links."""
    storage = request.app.storage
    domain_id = await storage.get_domain_id(request.host)
    url_toredir = await storage.get_urlredir(filename, domain_id)

    if not url_toredir:
        raise NotFound('No shortened links found with this name '
                       'on this domain.')

    return response.redirect(url_toredir)


@bp.post('/api/shorten')
async def shorten_handler(request):
    """Handles addition of shortened links."""

    user_id = await token_check(request)
    try:
        url_toredir = str(request.json['url'])
        url_parsed = urllib.parse.urlparse(url_toredir)
    except (TypeError, ValueError):
        raise BadInput('Invalid URL')

    if url_parsed.scheme not in ('https', 'http'):
        raise BadInput(f'Invalid URI scheme({url_parsed.scheme}). '
                       'Only https and http are allowed.')

    # Check if admin is set in get values, if not, do checks
    # If it is set, and the admin value is truthy, do not do checks
    do_checks = not ('admin' in request.args and request.args['admin'])

    # Let's actually check if the user is an admin
    # and raise an error if they're not an admin
    if not do_checks:
        await check_admin(request, user_id, True)

    # Skip checks for admins
    if do_checks:
        if not request.app.econfig.SHORTENS_ENABLED:
            raise FeatureDisabled('shortens are currently disabled')

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

    domain_id, subdomain_name, domain = await get_domain_info(request,
                                                              user_id,
                                                              FileNameType.SHORTEN)
    domain = transform_wildcard(domain, subdomain_name)

    await request.app.db.execute("""
    INSERT INTO shortens (shorten_id, filename,
        uploader, redirto, domain)
    VALUES ($1, $2, $3, $4, $5)
    """, redir_id, redir_rname, user_id, url_toredir, domain_id)

    # appended to generated filename
    dpath = pathlib.Path(domain)
    fpath = dpath / 's' / f'{redir_rname}'

    return response.json({
        'url': f'https://{str(fpath)}'
    })
