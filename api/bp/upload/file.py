# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os
from pathlib import Path
from typing import Optional

from quart import request, current_app as app
from api.common import calculate_hash
from api.errors import BadUpload


class UploadFile:
    def __init__(self, data):
        self.storage = data
        self.name: str = data.filename
        self.size: int = data.content_length
        assert self.size is not None
        self.stream = data.stream
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
        return str(self.path.resolve())

    def calculate_size(self, multiplier) -> int:
        """
        Calculates the size of this file, with the dupe multiplier applied if
        necessary.
        """
        file_size = self.size
        # TODO self.path can be optional, check for it in here
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
        self.stream.seek(0)
        self.hash = await calculate_hash(self.stream)
        self.stream.seek(0)

    async def resolve(self, extension: str) -> None:
        await self._hash_file()
        assert self.hash is not None
        folder = app.econfig.IMAGE_FOLDER
        raw_path = f"{folder}/{self.hash[0]}/{self.hash}{extension}"
        self.path = Path(raw_path)
