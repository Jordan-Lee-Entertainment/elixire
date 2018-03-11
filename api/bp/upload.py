import pathlib
import asyncio
import logging
import time
import mimetypes
import os
import io

from sanic import Blueprint
from sanic import response

from ..common_auth import token_check, check_admin
from ..common import gen_filename
from ..snowflake import get_snowflake
from ..errors import BadImage, Ratelimited

import PIL.Image
import PIL.ExifTags

bp = Blueprint('upload')
log = logging.getLogger(__name__)


async def scan_webhook(app, user_id: int, filename: str,
                       filesize: int, scan_out: str):
    """Execute a discord webhook with information about the virus scan."""
    uname = await app.db.fetchval("""
        select username
        from users
        where user_id = $1
    """, user_id)

    webhook_payload = {
        'embeds': [{
            'title': 'Elixire Virus Scanning',
            'color': 0xff0000,
            'fields': [
                {
                    'name': 'user',
                    'value': f'id: {user_id}, username: {uname}'
                },

                {
                    'name': 'file info',
                    'value': f'filename: `{filename}`, {filesize} bytes'
                },

                {
                    'name': 'clamdscan out',
                    'value': f'```\n{scan_out}\n```'
                }
            ]
        }],
    }

    async with app.session.post(app.econfig.UPLOAD_SCAN_WEBHOOK,
                                json=webhook_payload) as resp:
        return resp


async def scan_file(request, **kwargs):
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """
    filebody = kwargs.get('filebody')
    filesize = kwargs.get('filesize')
    filename = kwargs.get('filename')
    user_id = kwargs.get('user_id')

    app = request.app

    if not request.app.econfig.UPLOAD_SCAN:
        log.warning('Scans are disabled.')
        return

    # time to check clamdscan
    scanstart = time.monotonic()
    scanproc = await asyncio.create_subprocess_shell(
        "clamdscan -i -m --no-summary -",
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
    )

    # combine outputs
    out, err = map(lambda s: s.decode('utf-8'),
                   await scanproc.communicate(input=filebody))
    scanend = time.monotonic()

    delta = round(scanend - scanstart, 6)
    log.info(f'Scanning {filesize/1024/1024} MB took {delta} seconds')

    complete = f'{out}{err}'
    log.debug(f'output of clamdscan: {complete}')

    if 'OK' not in complete:
        # Oops.
        log.warning(f'user id {user_id} did a dumb')
        await scan_webhook(app, user_id, filename, filesize, complete)
        raise BadImage('Image contains a virus.')


async def clear_exif(image_bytes):
    """Clears exif data of given image.

    Doesn't check if the image is a JPEG, assumes that it is.
    """
    image = PIL.Image.open(io.BytesIO(image_bytes))
    # Check if image has exif at all, return if not
    if not image._getexif():
        return image_bytes

    orientation_exif = PIL.ExifTags.TAGS[274]
    exif = dict(image._getexif().items())

    # Only clear exif if orientation exif is present
    # We're not just returning as re-saving image removes the
    # remaining exif tags (like location or device info)
    if orientation_exif in exif:
        if exif[orientation_exif] == 3:
            image = image.rotate(180, expand=True)
        elif exif[orientation_exif] == 6:
            image = image.rotate(270, expand=True)
        elif exif[orientation_exif] == 8:
            image = image.rotate(90, expand=True)

    result_bytes = io.BytesIO()
    image.save(result_bytes, format='JPEG')
    image.close()
    return result_bytes.getvalue()


@bp.post('/api/upload')
async def upload_handler(request):
    """
    True hell happens in this function.

    We need to check a lot of shit around here.

    If things crash, we die.
    """
    user_id = await token_check(request)
    keys = request.files.keys()

    # Check if admin is set in get values, if not, do checks
    # If it is set, and the admin value is truthy, do not do checks
    do_checks = not ('admin' in request.args and request.args['admin'])

    # Let's actually check if the user is an admin
    # and raise an error if they're not an admin
    if not do_checks:
        await check_admin(request, user_id, True)

    # the first, and only the first.
    key = next(iter(keys))
    filedata = request.files[key]
    filedata = next(iter(filedata))

    # filedata contains type, body and name
    in_filename = filedata.name
    filemime = filedata.type
    filebody = filedata.body
    given_extension = os.path.splitext(in_filename)[-1].lower()
    # For admins, use the extension
    extension = given_extension

    filesize = len(filebody)

    # Skip checks for admins
    if do_checks:
        # check mimetype
        if filemime not in request.app.econfig.ACCEPTED_MIMES:
            raise BadImage('bad image type')

        used = await request.app.db.fetchval("""
        SELECT SUM(file_size)
        FROM files
        WHERE uploader = $1
        AND file_id > time_snowflake(now() - interval '7 days')
        """, user_id)

        byte_limit = await request.app.db.fetchval("""
        SELECT blimit
        FROM limits
        WHERE user_id = $1
        """, user_id)

        if used and used > byte_limit:
            cnv_limit = byte_limit / 1024 / 1024
            raise Ratelimited('You already blew your weekly'
                              f' limit of {cnv_limit}MB')

        if used and used + filesize > byte_limit:
            cnv_limit = byte_limit / 1024 / 1024
            raise Ratelimited('This file blows the weekly limit of'
                              f' {cnv_limit}MB')

        # all good with limits
        await scan_file(request,
                        filebody=filebody, filename=in_filename,
                        filesize=filesize, user_id=user_id)

        extension = f".{filemime.split('/')[-1]}"

        # Get all possible extensions
        pot_extensions = mimetypes.guess_all_extensions(filemime)
        # if there's any potentials, check if the extension supplied by user
        # is in potentials, and if it is, use the extension by user
        # if it is not, use the first potential extension
        # and if there's no potentials, just use the last part of mimetype
        if pot_extensions:
            extension = (given_extension if given_extension in pot_extensions
                         else pot_extensions[0])

    file_rname = await gen_filename(request)
    file_id = get_snowflake()

    fspath = f'./images/{file_rname}{extension}'

    await request.app.db.execute("""
    INSERT INTO files (file_id, mimetype, filename,
        file_size, uploader, fspath)
    VALUES ($1, $2, $3, $4, $5, $6)
    """, file_id, filemime, file_rname,
                                 filesize, user_id, fspath)

    if filemime == "image/jpeg" and request.app.econfig.CLEAR_EXIF:
        filebody = await clear_exif(filebody)

    # write to fs
    with open(fspath, 'wb') as fd:
        fd.write(filebody)

    # get domain ID from user and return it
    domain_id = await request.app.db.fetchval("""
    SELECT domain
    FROM users
    WHERE user_id = $1
    """, user_id)

    domain = await request.app.db.fetchval("""
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """, domain_id)

    # appended to generated filename
    dpath = pathlib.Path(domain)
    fpath = dpath / 'i' / f'{file_rname}{extension}'

    return response.json({
        'url': f'https://{str(fpath)}'
    })
