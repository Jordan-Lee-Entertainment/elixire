# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import io
from pathlib import Path
from typing import Optional

from quart import request, current_app as app

from api.common import calculate_hash
from api.errors import BadUpload


class UploadFile:
    def __init__(self, data):
        self.name: str = data.filename
        self.size: int = data.stream.getbuffer().nbytes
        self.stream: io.BytesIO = data.stream
        self.mime: str = data.mimetype

        self.hash: Optional[str] = None
        self.path: Optional[Path] = None

    @property
    def given_extension(self):
        """
        The file extension from the given filename.
        """
        return os.path.splitext(self.name)[-1].lower()

    @property
    def raw_path(self) -> str:
        """
        Returns the path to this file on the filesystem as a str.
        """
        if self.path is None:
            raise ValueError("path not initialized")

        return str(self.path.resolve())

    def calculate_size(self, multiplier) -> int:
        """
        Calculates the size of this file, with the dupe multiplier applied if
        necessary.
        """
        file_size = self.size

        if self.path is not None and self.path.exists():
            file_size *= multiplier

        return file_size

    @classmethod
    async def from_request(cls):
        """Make an UploadFile from the current request context."""
        # get the first file in the request
        files = await request.files

        try:
            key = next(iter(files.keys()))
        except StopIteration:
            raise BadUpload("No images given")

        return cls(files[key])

    async def _gen_hash(self):
        """Hash the given file. The output hash is given via the
        :attr:`hash` attribute."""
        self.hash = await calculate_hash(self.stream)
        self.stream.seek(0)

    async def resolve(self, extension):
        """Resolve the file's path. It is inserted into :attr:`path`."""
        await self._gen_hash()
        folder = app.econfig.IMAGE_FOLDER
        raw_path = f"{folder}/{self.hash[0]}/{self.hash}{extension}"
        self.path = Path(raw_path)
