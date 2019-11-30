# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import io
import logging
import mimetypes
from dataclasses import dataclass
from typing import Optional, Tuple

import magic
from quart import current_app as app

from api.bp.upload.exif import clear_exif
from api.bp.upload.virus import scan_file
from api.common.webhook import jpeg_toobig_webhook
from api.errors import BadImage, FeatureDisabled, QuotaExploded
from .file import UploadFile

__all__ = ["UploadContext"]
log = logging.getLogger(__name__)

FORCE_EXTENSION = {"image/jpeg": ".jpg"}


@dataclass
class UploadContext:
    """Represents the context of a file upload.

    Attributes:
     - file: UploadFile
        The file being uploaded.
     - user_id: int
        The user id representing the user that is uploading.
     - shortname: str
        The shortname of the file
     - do_checks: bool
        If checks regarding validity of the file should be done.
        Set to false on admin uploads
     - start_timestamp: int
        The starting timestamp of this current upload.
        Use time.monotonic for this value.

    Properties:
     - mime: str
        The mimetype of the file. Uses the first 1024 bytes of the file, then
        runs them through libmagic and caches the result.
    """

    file: UploadFile
    user_id: int
    shortname: str
    do_checks: bool
    start_timestamp: int
    _mime: Optional[str] = None

    async def strip_exif(self) -> io.BytesIO:
        """Strip EXIF information from a given file."""
        stream = self.file.stream
        if not app.econfig.CLEAR_EXIF or self.file.mime != "image/jpeg":
            log.debug("not stripping exif, disabled or not jpeg")
            return stream

        log.debug("going to clear exif now")
        ratio_limit = app.econfig.EXIF_INCREASELIMIT

        noexif_stream = await clear_exif(stream, loop=app.loop)
        noexif_len = len(noexif_stream.getvalue())
        ratio = noexif_len / self.file.size

        # if this is an admin upload or the file hasn't grown big, return the
        # stripped exif buffer
        #
        # (admins get to always have their jpegs stripped of exif data)
        if not self.do_checks or ratio < ratio_limit:
            return noexif_stream

        # or else... send a webhook about what happened
        if ratio > ratio_limit:
            await jpeg_toobig_webhook(self, noexif_len)
            raise BadImage("JPEG file is too big")

        return self.file.stream

    @property
    async def mime(self) -> str:
        if self._mime is None:
            self.file.stream.seek(0)
            chunk = self.file.stream.read(1024)
            self.file.stream.seek(0)

            # TODO check failure, return None
            self._mime = magic.from_buffer(chunk, mime=True)

        return self._mime

    async def resolve_mime(self) -> Tuple[str, str]:
        """Resolve the of the upload file.

        Returns the MIME of the file and the extension of the file.
        """
        # TODO check None and raise BadImage if do_checks is on
        # but instead use file.mime if do_checks is off
        mimetype = await self.mime

        if self.do_checks and mimetype not in app.econfig.ACCEPTED_MIMES:
            raise BadImage(f"Bad mime type: {mimetype!r}")

        try:
            extensions = [FORCE_EXTENSION[mimetype]]
        except KeyError:
            extensions = mimetypes.guess_all_extensions(mimetype)

        assert extensions

        # we use file.given_extension ONLY WHEN it exists in the
        # extensions list. this disallows users to e.g set .jpe
        # when mimetype is image/jpeg, because FORCE_EXTENSION will only give
        # .jpeg available.
        extension = self.file.given_extension
        if extension not in extensions:
            extension = extensions[0]

        return mimetype, extension

    async def perform_checks(self) -> None:
        """Perform higher level checks"""
        if not self.do_checks:
            return

        if not app.econfig.UPLOADS_ENABLED:
            raise FeatureDisabled("Uploads are currently disabled")

        await self.check_limits()
        await scan_file(self)

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
