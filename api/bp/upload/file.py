# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import io
import os
from pathlib import Path
from typing import Optional

from api.common import calculate_hash
from api.errors import BadUpload


class UploadFile:
    def __init__(self, data):
        self.name: str = data.name
        self.body = data.body
        self.size: int = len(self.body)
        self.io = io.BytesIO(self.body)
        self.mime: str = data.type

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
        if self.path.exists():
            file_size *= multiplier
        return file_size

    @classmethod
    def from_request(cls, request):
        # get the first file in the request
        try:
            key = next(iter(request.files.keys()))
        except StopIteration:
            raise BadUpload('No images given')

        data = next(iter(request.files[key]))

        return cls(data)

    async def hash_file(self, app):
        self.hash = await calculate_hash(app, io.BytesIO(self.body))

    async def resolve(self, app, extension):
        folder = app.econfig.IMAGE_FOLDER

        raw_path = f'{folder}/{self.hash[0]}/{self.hash}{extension}'
        self.path = Path(raw_path)
