import pathlib
from sanic import Blueprint
from sanic import response

from ..common_auth import token_check
from ..common import gen_filename
from ..snowflake import get_snowflake
from ..errors import BadImage, BadUpload

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

    # check mimetype
    if filemime not in ACCEPTED_MIMES:
        return BadImage('bad image type')

    filesize = len(filebody)
    # TODO: check limits using filesize

    file_rname = await gen_filename(request)
    file_id = get_snowflake()

    await request.app.db.execute("""
    INSERT INTO files (file_id, mimetype, filename,
        file_size, uploader, fspath)
    VALUES ($1, $2, $3, $4, $5, $6)
    """, file_id, filemime, file_rname,
                                 filesize, user_id, "")

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
    extension = filemime.split('/')[-1]
    fpath = dpath / f'{file_rname}.{extension}'

    return response.json({
        'url': f'https://{str(fpath)}'
    })

