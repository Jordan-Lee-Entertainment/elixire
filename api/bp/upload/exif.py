# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import functools
import logging
import io

import PIL.Image

EXIF_ORIENTATION = 274
log = logging.getLogger(__name__)


async def clear_exif(image_bytes: io.BytesIO, loop) -> io.BytesIO:
    """Clears exif data of given image.

    Assumes a JPEG image.
    """
    image = PIL.Image.open(image_bytes)

    exif = image._getexif()
    if not exif:
        log.debug('not resaving, no exif data was present')
        return image_bytes

    # Only clear exif if orientation exif is present
    # We're not just returning as re-saving image removes the
    # remaining exif tags (like location or device info)
    if EXIF_ORIENTATION in exif:
        log.debug(f'exif orientation: {exif[EXIF_ORIENTATION]}')
        if exif[EXIF_ORIENTATION] == 3:
            image = image.rotate(180, expand=True)
        elif exif[EXIF_ORIENTATION] == 6:
            image = image.rotate(270, expand=True)
        elif exif[EXIF_ORIENTATION] == 8:
            image = image.rotate(90, expand=True)
    else:
        log.debug('no exif orientation value')

    log.debug('resaving jpeg')
    result_bytes = io.BytesIO()

    save = functools.partial(image.save, result_bytes, format='JPEG')
    await loop.run_in_executor(None, save)

    image.close()
    return result_bytes
