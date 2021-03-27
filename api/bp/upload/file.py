# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
import io
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from collections import namedtuple

from quart import request, current_app as app

from api.common import calculate_hash
from api.errors import BadUpload

BaseFile = namedtuple("BaseFile", "filename stream mimetype")


@dataclass
class UploadFile:
    # TODO docstring

    name: str
    size: int
    stream: io.BytesIO
    mime: str

    hash: Optional[str] = None
    path: Optional[Path] = None
    id: Optional[int] = None

    def __init__(self, data):
        self.name = data.filename
        self.size = data.content_length
        assert self.size is not None
        self.stream = data.stream
        self.mime = data.mimetype

        self.hash = None
        self.path = None
        self.id = None

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
        # this works by getting all the files, then getting the first one.
        files = await request.files

        try:
            key = next(iter(files.keys()))
        except StopIteration:
            raise BadUpload("No images given")

        return cls(files[key])

    @classmethod
    def from_stream(
        cls, filename: str, stream: io.BytesIO, mimetype: str
    ) -> "UploadFile":
        wrapped_file = BaseFile(filename=filename, stream=stream, mimetype=mimetype)
        return cls(wrapped_file)

    async def _gen_hash(self):
        """Hash the given file. The output hash is given via the
        :attr:`hash` attribute."""
        self.stream.seek(0)
        self.hash = await calculate_hash(self.stream)
        self.stream.seek(0)

    async def resolve(self, extension):
        """Resolve the file's path. It is inserted into :attr:`path`."""
        await self._gen_hash()
        folder = app.econfig.IMAGE_FOLDER
        raw_path = f"{folder}/{self.hash[0]}/{self.hash}{extension}"
        self.path = Path(raw_path)
