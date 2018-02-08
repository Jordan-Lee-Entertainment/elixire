from sanic import Blueprint
from sanic import response

bp = Blueprint('fetch')


@bp.get('/i/<filename:str>.<extension:str>')
async def file_handler(request, filename, extension):
    """This blueprint is unused.

    Right now, we use app.add_static to map ./images to /i

    This will change someday (since we plan to use s3 or b2).
    We gotta be ready
    """
    return await response.file(f'./images/{filename}.{extension}')
