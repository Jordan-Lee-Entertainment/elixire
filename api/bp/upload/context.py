# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import io
import logging
import mimetypes
from collections import namedtuple

import magic
from quart import current_app as app

from api.bp.upload.exif import clear_exif
from api.bp.upload.virus import scan_file
from api.common.webhook import jpeg_toobig_webhook
from api.errors import BadImage, FeatureDisabled, QuotaExploded

__all__ = ["UploadContext"]
log = logging.getLogger(__name__)


class UploadContext(
    namedtuple(
        "UploadContext",
        [
            "file",  # the UploadFile that is being uploaded
            "user_id",  # user id that is uploading
            "shortname",  # shortname of the file
            "do_checks",  # True if checks will be performed
            "start_timestamp",  # the start timestamp of this upload
        ],
    )
):
    async def strip_exif(self) -> io.BytesIO:
        """Strip EXIF information from a given file."""
        stream = self.file.stream
        if not app.econfig.CLEAR_EXIF or self.file.mime != "image/jpeg":
            log.debug("not stripping exif, disabled or not jpeg")
            return stream

        log.debug("going to clear exif now")
        ratio_limit = app.econfig.EXIF_INCREASELIMIT

        noexif_body = await clear_exif(stream, loop=app.loop)
        noexif_len = len(noexif_body.getvalue())
        ratio = noexif_len / self.file.size

        # if this is an admin upload or the file hasn't grown big, return the
        # stripped exif buffer
        #
        # (admins get to always have their jpegs stripped of exif data)
        if not self.do_checks or ratio < ratio_limit:
            return noexif_body

        # or else... send a webhook about what happened
        elif ratio > ratio_limit:
            await jpeg_toobig_webhook(app, self, noexif_len)

        return self.file.io

    def get_mime(self, file_body):
        return magic.from_buffer(file_body, mime=True)

    async def perform_checks(self, app) -> str:
        given_extension = self.file.given_extension

        if not app.econfig.UPLOADS_ENABLED:
            raise FeatureDisabled("Uploads are currently disabled")

        # to get the mime we extract only the first 512 bytes
        self.file.stream.seek(0)
        chunk = self.file.stream.read(512)
        self.file.stream.seek(0)

        mimetype = await app.loop.run_in_executor(None, self.get_mime, chunk)

        # Check if file's mimetype is in allowed mimetypes
        if mimetype not in app.econfig.ACCEPTED_MIMES:
            raise BadImage(f"Bad mime type: {mimetype!r}")

        # check file upload limits
        await self.check_limits(app)

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

        return extension

    async def check_limits(self, app):
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
