# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

import PIL.Image

EXIF_ORIENTATION = 274
log = logging.getLogger(__name__)


def clear_exif(filepath: str) -> None:
    image = PIL.Image.open(filepath)

    exif = image._getexif()
    if not exif:
        log.debug("not resaving, no exif data was present")
        return

    # Only clear exif if orientation exif is present
    # We're not just returning as re-saving image removes the
    # remaining exif tags (like location or device info)
    if EXIF_ORIENTATION in exif:
        log.debug(f"exif orientation: {exif[EXIF_ORIENTATION]}")
        if exif[EXIF_ORIENTATION] == 3:
            image = image.rotate(180, expand=True)
        elif exif[EXIF_ORIENTATION] == 6:
            image = image.rotate(270, expand=True)
        elif exif[EXIF_ORIENTATION] == 8:
            image = image.rotate(90, expand=True)
    else:
        log.debug("no exif orientation value")

    log.debug("saving")
    image.save(filepath, format="JPEG")
    image.close()
