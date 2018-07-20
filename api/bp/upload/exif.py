import io

import PIL.ExifTags
import PIL.Image

from api.common.webhook import jpeg_toobig_webhook


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
