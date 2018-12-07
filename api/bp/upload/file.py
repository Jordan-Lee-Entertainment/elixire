"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

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
