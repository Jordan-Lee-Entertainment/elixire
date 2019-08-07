# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

__all__ = [
    "choice_repeat",
    "png_data",
    "token",
    "hexs",
    "username",
    "email",
    "png_request",
]

import base64
import io
import random
import secrets
import string
from typing import Tuple

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


async def png_request() -> Tuple[dict, bytes]:
    """Generate headers and a body to send containing a PNG file."""
    form = aiohttp.FormData()
    form.add_field("file", png_data(), filename="random.png", content_type="image/png")
    writer = form._gen_form_data()

    body = _AsyncBytesIO()
    await writer.write(body)

    return (
        {"content-type": f"multipart/form-data; boundary={writer._boundary_value}"},
        body.stream.getvalue(),
    )


def token() -> str:
    return secrets.token_urlsafe(random.randint(100, 300))


def hexs(len: int = 5) -> str:
    return secrets.token_hex(len)


def username() -> str:
    return hexs(6)


def email() -> str:
    name = hexs()
    domain = hexs()

    return f"{name}@{domain}.com"
