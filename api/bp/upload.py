import pathlib
import asyncio
import logging
import time
import mimetypes
import os
import io
from collections import namedtuple

import PIL.Image
import PIL.ExifTags

from sanic import Blueprint
from sanic import response

from ..common.auth import gen_shortname, check_admin
from ..common import get_domain_info, transform_wildcard, \
    delete_file, calculate_hash, get_random_domain
from ..common.webhook import jpeg_toobig_webhook, scan_webhook
from ..snowflake import get_snowflake
from ..errors import BadImage, QuotaExploded, BadUpload, FeatureDisabled
from ..decorators import auth_route
from ..permissions import Permissions, domain_permissions
from .metrics import is_consenting, submit


bp = Blueprint('upload')
log = logging.getLogger(__name__)
UploadContext = namedtuple('UploadContext',
                           'user_id mime inputname shortname size '
                           'body bytes checks start_timestamp')


async def actual_scan_file(app, ctx):
    """Scan a file for viruses using clamdscan.

    Raises BadImage on any non-successful scan.
    """
    if not app.econfig.UPLOAD_SCAN:
        log.warning('Scans are disabled.')
        return

    scanstart = time.monotonic()
    scanproc = await asyncio.create_subprocess_shell(
        "clamdscan -i -m --no-summary -",
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
    )

    # combine outputs
    out, err = map(lambda s: s.decode('utf-8'),
                   await scanproc.communicate(input=ctx.body))
    out = f'{out}{err}'
    scanend = time.monotonic()

    delta = round(scanend - scanstart, 6)
    log.info(f'Scanning {ctx.size/1024/1024} MB took {delta} seconds')
    log.debug(f'output of clamdscan: {out}')

    if 'OK' not in out:
        # Oops.
        log.warning(f'user id {ctx.user_id} did a dumb')
        await scan_webhook(app, ctx, out)
        raise BadImage('Image contains a virus.')


async def scan_background(app, corotask, ctx):
    """Run an existing scanning task in the background."""
    done, not_done = await asyncio.wait([corotask])
    done = iter(done)
    not_done = iter(not_done)

    try:
        task = next(done)

        exc = task.exception()
        if exc is not None and isinstance(exc, BadImage):
            # delete image when BadImage was raised.
            fspath = await app.db.fetchval("""
            SELECT fspath
            FROM files
            WHERE filename = $1
            """, ctx.shortname)

            if not fspath:
                log.warning(f'File {ctx.shortname} was '
                            'deleted when scan finished')

            try:
                os.remove(fspath)
            except OSError:
                log.warning(f'File path {fspath!r} was deleted')

            await delete_file(app, ctx.shortname, None, False)
            log.info(f'Deleted file {ctx.shortname}')

        elif exc is not None:
            log.exception('Error in background scan')
        else:
            log.info(f'Background scan for {ctx.inputname} is OK')
    except StopIteration:
        log.exception('background scan task did not finish, how??')


async def scan_file(app, ctx):
    """Run a scan on a file.

    Schedules the scanning on the background if it takes too
    long to scan the file in question.
    """
    coro = actual_scan_file(app, ctx)
    done, not_done = await asyncio.wait([coro],
                                        timeout=app.econfig.SCAN_WAIT_THRESHOLD)

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
        log.info('Scheduled background scan on '
                 f'{ctx.inputname} | {ctx.shortname}')
        app.loop.create_task(scan_background(app, corotask, ctx))


async def clear_exif(image_bytes: io.BytesIO) -> io.BytesIO:
    """Clears exif data of given image.

    Assumes a JPEG image.
    """
    image = PIL.Image.open(image_bytes)

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
    return result_bytes


async def check_limits(app, ctx):
    """Check if the user can upload the file."""
    user_id = ctx.user_id

    # check user's limits
    used = await app.db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    AND file_id > time_snowflake(now() - interval '7 days')
    """, user_id)

    byte_limit = await app.db.fetchval("""
    SELECT blimit
    FROM limits
    WHERE user_id = $1
    """, user_id)

    # convert to megabytes so we display to the user
    cnv_limit = byte_limit / 1024 / 1024

    if used and used > byte_limit:
        raise QuotaExploded('You already blew your weekly'
                            f' limit of {cnv_limit}MB')

    if used and used + ctx.size > byte_limit:
        raise QuotaExploded('This file blows the weekly limit of'
                            f' {cnv_limit}MB')


async def upload_checks(app, ctx: UploadContext,
                        given_extension: str) -> tuple:
    """Do some upload checks."""
    if not app.econfig.UPLOADS_ENABLED:
        raise FeatureDisabled('Uploads are currently disabled')

    # check mimetype
    if ctx.mime not in app.econfig.ACCEPTED_MIMES:
        raise BadImage(f'Bad image mime type: {ctx.mime!r}')

    await check_limits(app, ctx)

    # check the file for viruses
    await scan_file(app, ctx)

    extension = f".{ctx.mime.split('/')[-1]}"

    # Get all possible extensions
    pot_extensions = mimetypes.guess_all_extensions(ctx.mime)

    # if there's any potentials, check if the extension supplied by user
    # is in potentials, and if it is, use the extension by user
    # if it is not, use the first potential extension
    # and if there's no potentials, just use the last part of mimetype
    if pot_extensions:
        extension = (given_extension if given_extension in pot_extensions
                     else pot_extensions[0])

    return extension


async def exif_checking(app, ctx) -> io.BytesIO:
    """Check exif information of the file.

    Returns the correct io.BytesIO instance to use
    when writing the file.
    """
    if not app.econfig.CLEAR_EXIF:
        return ctx.bytes

    if ctx.mime != 'image/jpeg':
        return ctx.bytes

    ratio_limit = app.econfig.EXIF_INCREASELIMIT
    noexif_body = await clear_exif(ctx.bytes)

    noexif_len = noexif_body.getbuffer().nbytes
    ratio = noexif_len / ctx.size

    # if this is an admin upload or the ratio is below the limit
    # reutrn the noexif'd bytes
    if not ctx.checks or ratio < ratio_limit:
        return noexif_body

    # or else... send a webhook about what happened
    elif ratio > ratio_limit:
        await jpeg_toobig_webhook(app, ctx, noexif_len)

    return ctx.bytes


def _construct_url(domain, shortname, extension):
    dpath = pathlib.Path(domain)
    final_path = dpath / 'i' / f'{shortname}{extension}'

    return f'https://{final_path!s}'


async def check_repeat(app, fspath: str, extension: str,
                       ctx: UploadContext) -> dict:
    # check which files have the same fspath (the same hash)
    files = await app.db.fetch("""
    SELECT filename, uploader, domain
    FROM files
    WHERE fspath = $1 AND files.deleted = false
    """, fspath)

    # get the first file, if any, from the uploader
    try:
        ufile = next(frow for frow in files if frow['uploader'] == ctx.user_id)
    except StopIteration:
        # no files for the user were found.
        return

    # fetch domain info about that file
    domain = await app.db.fetchval("""
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """, ufile['domain'])

    # use 'i' as subdomain by default
    # since files.subdomain isn't a thing.
    domain = transform_wildcard(domain, 'i')

    return {
        'url': _construct_url(domain, ufile['filename'], extension),
        'repeated': True,
        'shortname': ufile['filename'],
    }


async def upload_metrics(app, ctx):
    """Upload total time taken for procesisng to InfluxDB."""
    end = time.monotonic()
    delta = round((end - ctx.start_timestamp) * 1000, 5)

    await submit(app, 'upload_latency', delta, True)

    if await is_consenting(app, ctx.user_id):
        await submit(app, 'upload_latency_pub', delta, True)


def _fetch_domain(request):
    """Fetch domain information, if any"""
    try:
        given_domain = int(request.raw_args['domain'])
    except KeyError:
        given_domain = None

    try:
        given_subdomain = str(request.raw_args['subdomain'])
    except KeyError:
        given_subdomain = None

    return given_domain, given_subdomain


@bp.post('/api/upload')
@auth_route
async def upload_handler(request, user_id):
    """Main upload handler."""
    app = request.app

    # if admin is set on request.args, we will
    # do an "admin upload", without any checking for viruses,
    # weekly limits, etc.
    do_checks = not ('admin' in request.args and request.args['admin'])
    random_domain = ('random' in request.args and request.args['random'])
    given_domain, given_subdomain = _fetch_domain(request)

    # if the user is admin and they wanted an admin
    # upload, check if they're actually an admin
    if not do_checks:
        await check_admin(request, user_id, True)

    # we'll ignore any other files that are in the request
    try:
        key = next(iter(request.files.keys()))
    except StopIteration:
        raise BadUpload('No images given')

    filedata = request.files[key]
    filedata = next(iter(filedata))

    filebody = filedata.body
    filebytes = io.BytesIO(filebody)
    filesize = len(filebody)

    given_extension = os.path.splitext(filedata.name)[-1].lower()

    # by default, assume the extension given in the filename
    # is the one we should use.
    # this will be true if the upload is an admin upload.
    extension = given_extension

    # generate a filename so we can identify later when removing it
    # because of virus scanning.
    shortname = await gen_shortname(request, user_id)

    # construct an upload context
    ctx = UploadContext(user_id, filedata.type,
                        filedata.name, shortname, filesize,
                        filebody, filebytes, do_checks,
                        time.monotonic())

    if do_checks:
        extension = await upload_checks(app, ctx, given_extension)

    file_id = get_snowflake()

    imhash = await calculate_hash(app, filebytes)
    imfolder = app.econfig.IMAGE_FOLDER
    fspath = f'{imfolder}/{imhash[0]}/{imhash}{extension}'

    impath = pathlib.Path(fspath)

    if impath.exists():
        res = await check_repeat(app, fspath, extension, ctx)
        if res is not None:
            await upload_metrics(app, ctx)
            return response.json(res)

    domain_data = await get_domain_info(request, user_id)

    if random_domain:
        given_domain = await get_random_domain(app)

    domain_id = given_domain or domain_data[0]
    subdomain_name = given_subdomain or domain_data[1]

    # check if domain is uploadable
    await domain_permissions(app, domain_id, Permissions.UPLOAD)

    if given_domain is None:
        domain = domain_data[2]
    else:
        domain = await app.db.fetchval("""
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """, given_domain)

    domain = transform_wildcard(domain, subdomain_name)

    # for metrics
    app.file_upload_counter += 1

    if await is_consenting(app, user_id):
        app.upload_counter_pub += 1

    if impath.exists():
        filesize *= app.econfig.DUPE_DECREASE_FACTOR

    await app.db.execute("""
    INSERT INTO files (file_id, mimetype, filename,
        file_size, uploader, fspath, domain)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    """, file_id, ctx.mime, shortname, filesize, user_id, fspath, domain_id)

    correct_bytes = await exif_checking(app, ctx)
    with open(fspath, 'wb') as raw_file:
        raw_file.write(correct_bytes.getvalue())

    await upload_metrics(app, ctx)
    return response.json({
        'url': _construct_url(domain, shortname, extension),
        'shortname': shortname,
    })
