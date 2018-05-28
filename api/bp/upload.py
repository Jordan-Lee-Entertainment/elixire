import pathlib
import asyncio
import logging
import time
import mimetypes
import os
import io

from sanic import Blueprint
from sanic import response

from ..common_auth import token_check, check_admin, check_paranoid
from ..common import gen_filename, get_domain_info, transform_wildcard, delete_file
from ..snowflake import get_snowflake
from ..errors import BadImage, QuotaExploded, BadUpload, FeatureDisabled

import PIL.Image
import PIL.ExifTags

bp = Blueprint('upload')
log = logging.getLogger(__name__)


async def jpeg_toobig_webhook(app, user_id: int, in_filename: str,
                              out_filename: str, size_before: int,
                              size_after: int):
    wh_url = getattr(app.econfig, 'EXIF_TOOBIG_WEBHOOK', None)
    if not wh_url:
        return

    increase = size_after / size_before

    uname = await app.db.fetchval("""
        select username
        from users
        where user_id = $1
    """, user_id)

    payload = {
        'embeds': [{
            'title': 'Elixire EXIF Cleaner Size Change Warning',
            'color': 0x420420,
            'fields': [
                {
                    'name': 'user',
                    'value': f'id: {user_id}, name: {uname}'
                },
                {
                    'name': 'in filename',
                    'value': in_filename,
                },
                {
                    'name': 'out filename',
                    'value': out_filename,
                },
                {
                    'name': 'size change',
                    'value': f'{size_before}b -> {size_after}b '
                             f'({increase:.01f}x)',
                }
            ]
        }]
    }

    async with app.session.post(wh_url,
                                json=payload) as resp:
        return resp


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


async def actual_scan_file(request, **kwargs):
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """
    print('actual scan file here')
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

    return True


async def scan_background(request, corotask, **kwargs):
    """Run an existing scanning task in the background."""
    done, not_done = await asyncio.wait([corotask])
    done = iter(done)
    not_done = iter(not_done)

    filename = kwargs.get('filename')

    try:
        task = next(done)

        exc = task.exception()
        if exc is not None and isinstance(exc, BadImage):
            # pls delete image
            file_rname = kwargs.get('file_rname')

            fspath = await request.app.db.fetchval("""
            SELECT fspath
            FROM files
            WHERE filename = $1
            """, file_rname)

            if not fspath:
                log.warning(f'File {file_rname} was deleted when scan finished')

            try:
                os.remove(fspath)
            except OSError:
                log.warning(f'File path {fspath!r} was deleted')

            await delete_file(request, file_rname, None, False)
            log.info(f'Deleted file {file_rname}')

        elif exc is not None:
            log.exception('Error in background scan')
        else:
            log.info(f'Background scan for {filename} is OK')
    except StopIteration:
        log.exception('background scan task did not finish, how??')


async def scan_file(request, **kwargs):
    """Run a scan on a file."""
    coro = actual_scan_file(request, **kwargs)
    done, not_done = await asyncio.wait([coro], timeout=request.app.econfig.SCAN_WAIT_THRESHOLD)

    done = iter(done)
    not_done = iter(not_done)

    try:
        corotask = next(done)

        # if its already done in 5 seconds
        # and it is bad, please raise exc
        exc = corotask.exception()
        if exc is not None:
            raise exc

        log.info('scan file done')
    except StopIteration:
        corotask = next(not_done)

        # schedule a wait on the scan
        log.info(f'Scheduled background scan on {kwargs.get("filename")}')
        request.app.loop.create_task(scan_background(request, corotask, **kwargs))


async def clear_exif(image_bytes):
    """Clears exif data of given image.

    Doesn't check if the image is a JPEG, assumes that it is.
    """
    image = PIL.Image.open(io.BytesIO(image_bytes))
    # Check if image has exif at all, return if not
    rawexif = image._getexif()
    if not rawexif:
        return image_bytes

    orientation_exif = PIL.ExifTags.TAGS[274]
    exif = dict(rawexif.items())

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


async def upload_checks(request, user_id, filetup, given_extension) -> tuple:
    """Do some upload checks."""
    filemime, filesize, filebody, in_filename, file_rname = filetup

    if not request.app.econfig.UPLOADS_ENABLED:
        raise FeatureDisabled('uploads are currently disabled')

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
        raise QuotaExploded('You already blew your weekly'
                            f' limit of {cnv_limit}MB')

    if used and used + filesize > byte_limit:
        cnv_limit = byte_limit / 1024 / 1024
        raise QuotaExploded('This file blows the weekly limit of'
                            f' {cnv_limit}MB')

    # all good with limits
    await scan_file(request,
                    filebody=filebody, filename=in_filename,
                    filesize=filesize, user_id=user_id, file_rname=file_rname)

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

    return extension


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
    try:
        key = next(iter(keys))
    except StopIteration:
        raise BadUpload('No images given')

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

    # generate a filename so we can identify later when removing it
    # because of virus scanning.
    user_paranoid = await check_paranoid(request, user_id)
    fname_length = 8 if user_paranoid else 3
    file_rname = await gen_filename(request, fname_length)

    # Skip checks for admins
    if do_checks:
        extension = await upload_checks(request, user_id,
                                        (filemime, filesize,
                                         filebody, in_filename, file_rname),
                                        given_extension)

    file_id = get_snowflake()
    out_filename = file_rname + extension

    folder = request.app.econfig.IMAGE_FOLDER
    fspath = f'{folder}/{file_rname[0]}/{file_rname}{extension}'

    domain_id, subdomain_name, domain = await get_domain_info(request, user_id)
    domain = transform_wildcard(domain, subdomain_name)

    await request.app.db.execute("""
    INSERT INTO files (file_id, mimetype, filename,
        file_size, uploader, fspath, domain)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, file_id, filemime, file_rname,
                                 filesize, user_id, fspath, domain_id)

    if filemime == "image/jpeg" and request.app.econfig.CLEAR_EXIF:
        exif_limit = getattr(request.app.econfig, 'EXIF_INCREASELIMIT', None)
        noexif_filebody = await clear_exif(filebody)
        size_growth = (len(noexif_filebody) / filesize)

        # If admin mode or exif limit is disabled, just set the value
        # If growth is less than limit, also set the value
        if not do_checks or not exif_limit or size_growth < exif_limit:
            filebody = noexif_filebody
        # If there is a limit AND we're over the limit, then send warning
        elif exif_limit and size_growth > exif_limit:
            await jpeg_toobig_webhook(request.app, user_id, in_filename,
                                      out_filename, filesize,
                                      len(noexif_filebody))

    # write to fs
    with open(fspath, 'wb') as raw_file:
        raw_file.write(filebody)

    # appended to generated filename
    dpath = pathlib.Path(domain)
    fpath = dpath / 'i' / out_filename

    return response.json({
        'url': f'https://{str(fpath)}',
        'shortname': file_rname,
    })
