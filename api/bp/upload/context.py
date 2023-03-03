# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import functools
import logging
import mimetypes
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import magic
from quart import current_app as app

from api.bp.upload.exif import clear_exif
from api.bp.upload.virus import scan_file
from api.common.webhook import jpeg_toobig_webhook
from api.errors import BadImage, FeatureDisabled, QuotaExploded
from .file import UploadFile

__all__ = ["UploadContext"]
log = logging.getLogger(__name__)


@dataclass
class UploadContext:
    file: UploadFile
    user_id: int
    shortname: str
    do_checks: bool
    start_timestamp: int
    _computed_mime: Optional[str] = None

    async def strip_exif(self, filepath: str) -> None:
        if not app.cfg.CLEAR_EXIF or self.file.mime != "image/jpeg":
            log.debug("not stripping exif, disabled or not jpeg")
            return

        log.debug("going to clear exif now")
        ratio_limit = app.cfg.EXIF_INCREASELIMIT

        # Pillow is not async, so it is better to run
        # its relevant code on a thread
        blocking_exif_call = functools.partial(clear_exif, filepath)
        await app.loop.run_in_executor(None, blocking_exif_call)

        noexif_len = Path(filepath).stat().st_size
        ratio = noexif_len / self.file.size

        # or else... send a webhook about what happened
        if self.do_checks and ratio > ratio_limit:
            await jpeg_toobig_webhook(self, noexif_len)
            raise BadImage("jpeg-bomb attempt detected")

    @property
    async def mime(self) -> str:
        if self._computed_mime is None:
            with self.file.save_file_stream_position:
                chunk = self.file.stream.read(1024)

            # TODO check failure, return None
            mime_function = functools.partial(magic.from_buffer, mime=True)
            self._computed_mime = await app.loop.run_in_executor(
                None, mime_function, chunk
            )
            log.debug("computed mime: %r", self._computed_mime)

        return self._computed_mime

    async def perform_checks(self) -> str:
        given_extension = self.file.given_extension

        if not app.cfg.UPLOADS_ENABLED:
            raise FeatureDisabled("Uploads are currently disabled")

        # Get file's mimetype
        # TODO add error validation if self.mime is None
        mimetype = await self.mime

        # Check if file's mimetype is in allowed mimetypes
        if mimetype not in app.cfg.ACCEPTED_MIMES:
            raise BadImage(f"Bad mime type: {mimetype!r}")

        # check file upload limits
        await self.check_limits()

        # check the file for viruses
        await scan_file(self)

        # default to last part of mimetype
        extension = f".{self.file.mime.split('/')[-1]}"

        # get all possible file extensions for this type of file
        pot_extensions = mimetypes.guess_all_extensions(mimetype)

        # ban .bat uploads (at least with extension intact)
        if ".bat" in pot_extensions:
            pot_extensions.remove(".bat")

        # use the user-provided file extension if it's a valid extension for
        # this mimetype
        #
        # if it is not, use the first potential extension
        # and if there's no potentials, just use the last part of mimetype
        if pot_extensions:
            if given_extension in pot_extensions:
                extension = given_extension
            else:
                extension = pot_extensions[0]

        return mimetype, extension

    async def check_limits(self):
        user_id = self.user_id

        # check user's limits
        used = await app.db.fetchval(
            """
        SELECT SUM(file_size)
        FROM files
        WHERE uploader = $1
        AND file_id > time_snowflake(now() - interval '7 days')
        """,
            user_id,
        )

        byte_limit = await app.db.fetchval(
            """
        SELECT blimit
        FROM limits
        WHERE user_id = $1
        """,
            user_id,
        )

        # convert to megabytes so we display to the user
        cnv_limit = byte_limit / 1024 / 1024

        if used and used > byte_limit:
            raise QuotaExploded(f"You already blew your weekly limit of {cnv_limit} MB")

        if used and used + self.file.size > byte_limit:
            raise QuotaExploded(
                f"This file would blow the weekly limit of {cnv_limit} MB"
            )
