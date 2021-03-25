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
    "create_multipart",
    "rand_utf8",
]

import base64
import io
import random
import secrets
import string

from quart.testing import make_test_body_with_headers
from quart.datastructures import FileStorage


EMAIL_ALPHABET = string.ascii_lowercase


def choice_repeat(seq, length):
    return "".join([secrets.choice(seq) for _ in range(length)])


def png_data() -> io.BytesIO:
    # add 10 bytes of random data to prevent deduplication
    # when tests upload images
    base_png = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABC"
        b"AQAAAC1HAwCAAAAC0lEQVQYV2NgYAAAAAM"
        b"AAWgmWQ0AAAAASUVORK5CYII="
    )
    random_data = secrets.token_bytes(10)
    return io.BytesIO(base_png + random_data)


def token() -> str:
    return secrets.token_urlsafe(random.randint(100, 300))


def hexs(len: int = 5) -> str:
    return secrets.token_hex(len)


def username() -> str:
    return hexs(6)


def email() -> str:
    name = hexs()
    return f"{name}@discordapp.io"


async def create_multipart(data: io.BytesIO, filename: str, mimetype: str) -> dict:
    body, headers = make_test_body_with_headers(
        files={
            "file": FileStorage(
                stream=data,
                filename=f"{hexs(10)}.png",
                name="file",
                content_type="image/png",
            )
        }
    )

    return {"data": body, "headers": headers}


async def png_request() -> dict:
    """Generate keyword arguments to pass to an HTTP method function that would
    specify a multipart form body to upload a random PNG file.
    """
    return await create_multipart(png_data(), f"{hexs(10)}.png", "image/png")


def rand_utf8(chars: int) -> str:
    return "".join(
        random.sample(
            "".join(tuple(chr(i) for i in range(32, 0x110000) if chr(i).isprintable())),
            chars,
        )
    )
