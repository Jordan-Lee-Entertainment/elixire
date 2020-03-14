# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

__all__ = [
    "choice_repeat",
    "png_data",
    "token",
    "hexs",
    "username",
    "email",
    "png_request",
    "aiohttp_form",
]

import base64
import io
import random
import secrets
import string

import aiohttp


EMAIL_ALPHABET = string.ascii_lowercase


class _AsyncBytesIO:
    """Wrapper class for fake async operations under BytesIO."""

    def __init__(self):
        self.stream = io.BytesIO()

    async def write(self, data):
        self.stream.write(data)


def choice_repeat(seq, length):
    return "".join([secrets.choice(seq) for _ in range(length)])


def png_data() -> io.BytesIO:
    return io.BytesIO(
        base64.b64decode(
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABC"
            b"AQAAAC1HAwCAAAAC0lEQVQYV2NgYAAAAAM"
            b"AAWgmWQ0AAAAASUVORK5CYII="
        )
    )


def token() -> str:
    return secrets.token_urlsafe(random.randint(100, 300))


def hexs(len: int = 5) -> str:
    return secrets.token_hex(len)


def username() -> str:
    return hexs(6)


def email() -> str:
    name = hexs()
    return f"{name}@discordapp.io"


class FormData:
    """An abstraction over handling the creation of raw multipart form data.

    This is needed because Quart doesn't provide a facility to use multipart
    form data in its test client yet.

    To use it, construct it and use :meth:`add_field` to attach data. Then
    call :meth:`write` to generate the form data, then unpack the value of
    :attr:`request` into an HTTP method call on the test client.
    """

    def __init__(self):
        self.form = aiohttp.FormData()
        self.body = _AsyncBytesIO()
        self.writer = None

    def add_field(self, *args, **kwargs):
        return self.form.add_field(*args, **kwargs)

    async def write(self):
        self.writer = self.form._gen_form_data()
        await self.writer.write(self.body)

    @property
    def request(self):
        return {
            "headers": {
                "content-type": f"multipart/form-data; boundary={self.writer._boundary_value}"
            },
            "data": self.body.stream.getvalue(),
        }


async def aiohttp_form(data, filename: str, mimetype: str):
    fd = FormData()
    fd.add_field("file", data, filename=filename, content_type=mimetype)
    await fd.write()
    return fd.request


async def png_request() -> dict:
    """Generate keyword arguments to pass to an HTTP method function that would
    specify a multipart form body to upload a random PNG file.
    """
    return await aiohttp_form(png_data(), f"hexs(10).png", "image/png")
