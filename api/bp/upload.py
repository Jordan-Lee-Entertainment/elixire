import pathlib

from sanic import Blueprint
from sanic import response

from ..common_auth import token_check
from ..common import gen_filename
from ..snowflake import get_snowflake
from ..errors import BadImage, Ratelimited

bp = Blueprint('upload')


ACCEPTED_MIMES = [
    'image/png',
    'image/jpg',
    'image/jpeg'
]


@bp.post('/api/upload')
async def upload_handler(request):
    """
    True hell happens in this function.

    We need to check a lot of shit around here.

    If things crash, we die.
    """
    user_id = await token_check(request)
    keys = request.files.keys()

    # the first, and only the first.
    key = next(iter(keys))
    filedata = request.files[key]
    filedata = next(iter(filedata))

    # filedata contains type, body and name
    filemime = filedata.type
    filebody = filedata.body
    extension = filemime.split('/')[-1]

    # check mimetype
    if filemime not in ACCEPTED_MIMES:
        return BadImage('bad image type')

    used = await request.app.db.fetchval("""
    SELECT SUM(file_size)
    FROM files
    WHERE uploader = $1
    AND file_id > time_snowflake(now() - interval '7 hours')
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

    filesize = len(filebody)
    if used and used + filesize > byte_limit:
        cnv_limit = byte_limit / 1024 / 1024
        raise Ratelimited('This file blows the weekly limit of'
                          f' {cnv_limit}MB')

    # all good with limits
    file_rname = await gen_filename(request)
    file_id = get_snowflake()

    fspath = f'./images/{file_rname}.{extension}'

    await request.app.db.execute("""
    INSERT INTO files (file_id, mimetype, filename,
        file_size, uploader, fspath)
    VALUES ($1, $2, $3, $4, $5, $6)
    """, file_id, filemime, file_rname,
                                 filesize, user_id, fspath)

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
    fpath = dpath / f'{file_rname}.{extension}'

    return response.json({
        'url': f'https://{str(fpath)}'
    })

