# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

__all__ = ["choice_repeat", "png_data", "token", "hexs", "username", "email"]

import base64
import io
import random
import secrets
import string


EMAIL_ALPHABET = string.ascii_lowercase


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
    domain = hexs()

    return f"{name}@{domain}.com"
