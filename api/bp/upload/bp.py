import io
import logging
import mimetypes
import os
import pathlib
import time
from collections import namedtuple
from typing import Optional, Dict, Any

from sanic import Blueprint, response

from api.bp.upload.exif import exif_checking
from api.common import calculate_hash, get_domain_info, get_random_domain, transform_wildcard
from api.common.auth import check_admin, gen_shortname
from api.decorators import auth_route
from api.errors import BadImage, BadUpload, FeatureDisabled, QuotaExploded
from api.permissions import Permissions, domain_permissions
from api.snowflake import get_snowflake
from .virus import scan_file
from ..metrics import is_consenting, submit

bp = Blueprint('upload')
log = logging.getLogger(__name__)

UploadContext = namedtuple(
    'UploadContext',
    [
        'user_id',
        'mime',
        'inputname',
        'shortname',
        'size',
        'body',
        'bytes',
        'checks',
        'start_timestamp'
    ]
)


async def check_limits(app, ctx):
    """Check if the user can upload the file."""
    user_id = ctx.user_id

    # check user's limits
    used = await app.db.fetchval(
        """
        SELECT SUM(file_size)
        FROM files
        WHERE uploader = $1
        AND file_id > time_snowflake(now() - interval '7 days')
        """,
        user_id
    )

    byte_limit = await app.db.fetchval(
        """
        SELECT blimit
        FROM limits
        WHERE user_id = $1
        """,
        user_id
    )

    # convert to megabytes so we display to the user
    cnv_limit = byte_limit / 1024 / 1024

    if used and used > byte_limit:
        raise QuotaExploded(
            f'You already blew your weekly limit of {cnv_limit} MB'
        )

    if used and used + ctx.size > byte_limit:
        raise QuotaExploded(
            f'This file would blow the weekly limit of {cnv_limit} MB'
        )


async def upload_checks(app, ctx: UploadContext, given_extension: str) -> str:
    """Do some upload checks."""
    if not app.econfig.UPLOADS_ENABLED:
        raise FeatureDisabled('Uploads are currently disabled')

    # check mimetype
    if ctx.mime not in app.econfig.ACCEPTED_MIMES:
        raise BadImage(f'Bad image mime type: {ctx.mime!r}')

    # check file upload limits
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
        if given_extension in pot_extensions:
            extension = given_extension
        else:
            extension = pot_extensions[0]

    return extension


def _construct_url(domain, shortname, extension):
    dpath = pathlib.Path(domain)
    final_path = dpath / 'i' / f'{shortname}{extension}'

    return f'https://{final_path!s}'


async def check_repeat(app, fspath: str, extension: str, ctx: UploadContext) -> Optional[Dict[str, Any]]:
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

    log.info('Processing upload from %d', user_id)

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
    shortname, tries = await gen_shortname(request, user_id)
    await submit(app, 'shortname_gen_tries', tries, True)

    # construct an upload context
    ctx = UploadContext(
        user_id=user_id,
        mime=filedata.type,
        inputname=filedata.name,
        shortname=shortname,
        size=filesize,
        body=filebody,
        bytes=filebytes,
        checks=do_checks,
        start_timestamp=time.monotonic()
    )

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
        domain = await app.db.fetchval(
            """
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """,
            given_domain
        )

    domain = transform_wildcard(domain, subdomain_name)

    # for metrics
    app.file_upload_counter += 1

    if await is_consenting(app, user_id):
        app.upload_counter_pub += 1

    if impath.exists():
        filesize *= app.econfig.DUPE_DECREASE_FACTOR

    await app.db.execute(
        """
        INSERT INTO files (file_id, mimetype, filename,
            file_size, uploader, fspath, domain)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        file_id,
        ctx.mime,
        shortname,
        filesize,
        user_id,
        fspath,
        domain_id
    )

    correct_bytes = await exif_checking(app, ctx)
    with open(fspath, 'wb') as raw_file:
        raw_file.write(correct_bytes.getvalue())

    await upload_metrics(app, ctx)
    return response.json({
        'url': _construct_url(domain, shortname, extension),
        'shortname': shortname,
    })
