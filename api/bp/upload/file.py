# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
from pathlib import Path
from typing import Optional

from quart import request, current_app as app
from api.common import calculate_hash
from api.errors import BadUpload


class SavedFilePositionContext:
    def __init__(self, stream):
        self.stream = stream
        self.current_seek_position = None

    def __enter__(self):
        self.current_seek_position = self.stream.tell()
        self.stream.seek(0)

    def __exit__(self, type, value, traceback):
        assert self.current_seek_position is not None
        self.stream.seek(self.current_seek_position)


class UploadFile:
    def __init__(self, data):
        self.storage = data
        self.name: str = data.filename
        self.stream = data.stream
        self.mime: str = data.mimetype

        self.hash: Optional[str] = None
        self.path: Optional[Path] = None

        # initialize size with real stream position
        with self.save_file_stream_position:
            # find the size by seeking to 0 bytes from the end of the file
            self.stream.seek(0, os.SEEK_END)
            self.size = self.stream.tell()

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
        assert self.path
        return str(self.path.resolve())

    def calculate_size(self, multiplier) -> int:
        """
        Calculates the size of this file, with the dupe multiplier applied if
        necessary.
        """
        file_size = self.size
        assert self.path
        if self.path.exists():
            file_size *= multiplier
        return file_size

    @classmethod
    async def from_request(cls):
        # get the first file in the request
        files = await request.files
        try:
            key = next(iter(files.keys()))
        except StopIteration:
            raise BadUpload("No images given")

        return cls(files[key])

    async def _hash_file(self):
        with self.save_file_stream_position:
            self.hash = await calculate_hash(self.stream)

    async def resolve(self, extension: str) -> None:
        await self._hash_file()
        assert self.hash is not None
        folder = app.econfig.IMAGE_FOLDER
        raw_path = f"{folder}/{self.hash[0]}/{self.hash}{extension}"
        self.path = Path(raw_path)

    @property
    def save_file_stream_position(self) -> SavedFilePositionContext:
        return SavedFilePositionContext(self.stream)
