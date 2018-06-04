import string
import secrets
import os
import hashlib
import logging
from pathlib import Path
import time

import itsdangerous
import aiohttp

from .errors import FailedAuth, BadInput, NotFound

VERSION = '2.0.0'
ALPHABET = string.ascii_lowercase + string.digits
log = logging.getLogger(__name__)


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


def get_ip_addr(request) -> str:
    """Fetch the IP address for a request.

    Handles the cloudflare headers responsible to set
    the client's IP.
    """
    if 'X-Forwarded-For' not in request.headers:
        return request.ip
    return request.headers['X-Forwarded-For']


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


def calculate_hash(fhandler) -> str:
    """Generate a hash of the given file."""
    hashstart = time.monotonic()
    hash_obj = hashlib.sha256()

    for chunk in iter(lambda: fhandler.read(4096), b""):
        hash_obj.update(chunk)

    # so that we can reuse the same handler
    # later on
    fhandler.seek(0)

    hashend = time.monotonic()
    delta = round(hashend - hashstart, 6)
    log.info(f'Hashing file took {delta} seconds')

    return hash_obj.hexdigest()


async def gen_email_token(app, user_id, table: str, count: int = 0) -> str:
    """Generate a token for email usage"""
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
        raise BadInput('You already generated more than 3 tokens in the time period.')

    return possible


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


async def purge_cf(app, filename: str, ftype: int) -> int:
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

    if domain is None:
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

    return domain

async def delete_file(app, file_name, user_id, set_delete=True):
    """Delete a file, purging it from Cloudflare's cache."""
    domain_id = await purge_cf(app, file_name, FileNameType.FILE)

    if set_delete:
        exec_out = await app.db.execute("""
        UPDATE files
        SET deleted = true
        WHERE uploader = $1
        AND filename = $2
        AND deleted = false
        """, user_id, file_name)

        if exec_out == "UPDATE 0":
            raise NotFound('You have no files with this name.')

        fspath = await app.db.fetchval("""
        SELECT fspath
        FROM files
        WHERE uploader = $1
          AND filename = $2
        """, user_id, file_name)

        # fetch all files with the same fspath
        # and on the hash system, means the same hash
        same_fspath = await app.db.fetchval("""
        SELECT COUNT(*)
        FROM files
        WHERE fspath = $1 AND deleted = false
        """, fspath)

        if same_fspath == 0:
            path = Path(fspath)
            try:
                path.unlink()
                log.info(f'Deleted {fspath!s} since no files refer to it')
            except FileNotFoundError:
                log.warning(f'fspath {fspath!s} does not exist')
        else:
            log.info(f'there are still {same_fspath} files with the '
                     f'same fspath {fspath!s}, not deleting')
    else:
        if user_id:
            await app.db.execute("""
            DELETE FROM files
            WHERE
                filename = $1
            AND uploader = $2
            AND deleted = false
            """, file_name, user_id)
        else:
            await app.db.execute("""
            DELETE FROM files
            WHERE filename = $1
            AND deleted = false
            """, file_name)

    await app.storage.raw_invalidate(f'fspath:{domain_id}:{file_name}')


async def delete_shorten(app, shortname: str, user_id: int):
    """Remove a shorten from the system"""
    exec_out = await app.db.execute("""
    UPDATE shortens
    SET deleted = true
    WHERE uploader = $1
    AND filename = $2
    AND deleted = false
    """, user_id, shortname)

    # By doing this, we're cutting down DB calls by half
    # and it still checks for user
    if exec_out == "UPDATE 0":
        raise NotFound('You have no shortens with this name.')

    domain_id = await purge_cf(app, shortname, FileNameType.SHORTEN)
    await app.storage.raw_invalidate(f'redir:{domain_id}:{shortname}')



async def check_bans(request, user_id: int):
    """Check if the current user is already banned."""
    if user_id is not None:
        reason = await request.app.storage.get_ban(user_id)

        if reason:
            raise FailedAuth(f'User is banned. {reason}')

    ip_addr = get_ip_addr(request)
    ip_ban_reason = await request.app.storage.get_ipban(ip_addr)
    if ip_ban_reason:
        raise FailedAuth(f'IP address is currently banned. {ip_ban_reason}')


async def ban_webhook(app, user_id: int, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, 'USER_BAN_WEBHOOK', None)
    if not wh_url:
        return

    if isinstance(user_id, int):
        uname = await app.db.fetchval("""
            select username
            from users
            where user_id = $1
        """, user_id)
    else:
        uname = '<no username found>'

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


async def ip_ban_webhook(app, ip_address: str, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, 'IP_BAN_WEBHOOK', None)
    if not wh_url:
        return

    payload = {
        'embeds': [{
            'title': 'Elixire Auto IP Banning',
            'color': 0x696969,
            'fields': [
                {
                    'name': 'IP address',
                    'value': ip_address,
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


async def get_domain_info(request, user_id: int, dtype=FileNameType.FILE) -> tuple:
    """Get information about a user's selected domain."""
    domain_id, subdomain_name = await request.app.db.fetchrow("""
    SELECT domain, subdomain
    FROM users
    WHERE user_id = $1
    """, user_id)

    domain = await request.app.db.fetchval("""
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    if dtype == FileNameType.SHORTEN:
        shorten_domain_id, shorten_subdomain = await request.app.db.fetchrow("""
        SELECT shorten_domain, shorten_subdomain
        FROM users
        WHERE user_id = $1
        """, user_id)

        if shorten_domain_id is not None:
            shorten_domain = await request.app.db.fetchval("""
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """, shorten_domain_id)

            # if we have all the data on shorten subdomain, return it
            return shorten_domain_id, shorten_subdomain, shorten_domain

    return domain_id, subdomain_name, domain


def transform_wildcard(domain, subdomain_name):
    # Check if it's wildcard and if we have a subdomain set
    if domain[0:2] == "*." and subdomain_name:
        domain = domain.replace("*.", f"{subdomain_name}.")
    # If it's wildcard but we don't have a wildcard, upload to base domain
    elif domain[0:2] == "*.":
        domain = domain.replace("*.", "")

    return domain


async def send_email(app, user_email: str, subject: str, email_body: str):
    """Send an email to a user using the Mailgun API."""
    econfig = app.econfig
    mailgun_url = f'https://api.mailgun.net/v3/{econfig.MAILGUN_DOMAIN}/messages'

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
