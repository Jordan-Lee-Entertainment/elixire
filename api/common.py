import string
import secrets
import os

import itsdangerous

from .errors import FailedAuth

VERSION = '2.0.0'
ALPHABET = string.ascii_lowercase + string.digits


class TokenType:
    """Token type "enum"."""
    NONTIMED = 1
    TIMED = 2


class FileNameType:
    """Represents a type of a filename."""
    FILE = 0
    SHORTEN = 1


SIGNERS = {
    TokenType.TIMED: itsdangerous.TimestampSigner,
    TokenType.NONTIMED: itsdangerous.Signer,
}


def _gen_fname(length) -> str:
    """Generate a random filename."""
    return ''.join(secrets.choice(ALPHABET)
                   for _ in range(length))


async def gen_filename(request, length=3) -> str:
    """Generate a random filename, without clashes.

    This has a limit of generating a 10 character filename.
    Any attempts to get more characters will result
    in a RuntimeError.
    """
    if length > 10:
        raise RuntimeError('Failed to generate a filename')

    for _ in range(10):
        # generate random, check against db
        # if exists, continue loop
        # if not, return
        random_fname = _gen_fname(length)

        filerow = await request.app.db.fetchrow("""
        SELECT file_id
        FROM files
        WHERE filename = $1
        """, random_fname)

        if not filerow:
            return random_fname

    # if 10 tries didnt work, try generating with length+1
    return await gen_filename(request, length + 1)


async def _purge_cf_cache(app, purge_urls, email, apikey, zoneid):
    """Clear the Cloudflare cache for the given URLs and cf creds."""

    cf_purge_url = "https://api.cloudflare.com/client/v4/zones/"\
                   f"{zoneid}/purge_cache"

    cf_auth_headers = {
        'X-Auth-Email': email,
        'X-Auth-Key': apikey
    }

    purge_payload = {
        'files': purge_urls,
    }

    async with app.session.delete(cf_purge_url,
                                  json=purge_payload,
                                  headers=cf_auth_headers) as resp:
        return resp


def _purge_url_file(_filename: str, domain: str, detail: dict):
    """Generate a purge URL for a filename that represents a proper file."""
    joined = os.path.basename(detail['fspath'])
    return f'https://{domain}/i/{joined}'


def _purge_url_shorten(filename: str, domain: str, _detail: dict):
    """Generate a purge URL for a filename that represents a shortened url."""
    return f'https://{domain}/s/{filename}'


async def purge_cf(app, filename: str, ftype: int):
    """
    Purge a filename(that can represent either a proper file or a shorten)
    from Cloudflare's caching.
    """
    domain, detail = None, None

    if ftype == FileNameType.FILE:
        # query file_detail
        detail = await app.db.fetchrow("""
        SELECT domain, fspath
        FROM files
        WHERE filename = $1
        """, filename)

        domain = detail['domain']
    elif ftype == FileNameType.SHORTEN:
        # query shorten detail
        domain = await app.db.fetchval("""
        SELECT domain
        FROM shortens
        WHERE filename = $1
        """, filename)

    if not domain:
        # oops. invalid type?
        return

    domain_detail = await app.db.fetchrow("""
    SELECT domain, cf_enabled, cf_email, cf_zoneid, cf_apikey
    FROM domains
    WHERE domain_id = $1
    """, domain)

    # check if purge is enabled
    if domain_detail['cf_enabled']:
        mapping = {
            FileNameType.FILE: _purge_url_file,
            FileNameType.SHORTEN: _purge_url_shorten,
        }

        purge_url = mapping[ftype](filename, domain, detail)

        await _purge_cf_cache(app, [purge_url], domain_detail['cf_email'],
                              domain_detail['cf_apikey'],
                              domain_detail['cf_zoneid'])


async def check_bans(request, user_id: int):
    """Check if the current user is already banned."""

    # TODO: make this use Storage
    reason = await request.app.db.fetchval("""
    SELECT reason
    FROM bans
    WHERE user_id=$1 and now() < end_timestamp
    LIMIT 1
    """, user_id)

    if reason:
        raise FailedAuth(f'User is banned. {reason}')


async def ban_webhook(app, user_id: int, reason: str, period: str):
    wh_url = getattr(app.econfig, 'USER_BAN_WEBHOOK', None)
    if not wh_url:
        return

    uname = await app.db.fetchval("""
        select username
        from users
        where user_id = $1
    """, user_id)

    payload = {
        'embeds': [{
            'title': 'Elixire Auto Banning',
            'color': 0x696969,
            'fields': [
                {
                    'name': 'user',
                    'value': f'id: {user_id}, name: {uname}'
                },
                {
                    'name': 'reason',
                    'value': reason,
                },
                {
                    'name': 'period',
                    'value': period,
                }
            ]
        }]
    }

    async with app.session.post(wh_url,
                                json=payload) as resp:
        return resp
