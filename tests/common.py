# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import secrets
import random
import io
import base64
import string

EMAIL_ALPHABET = string.ascii_lowercase


def choice_repeat(seq, length):
    return "".join([secrets.choice(seq) for _ in range(length)])


def png_data():
    return io.BytesIO(
        base64.b64decode(
            b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABC"
            b"AQAAAC1HAwCAAAAC0lEQVQYV2NgYAAAAAM"
            b"AAWgmWQ0AAAAASUVORK5CYII="
        )
    )


def hexs(len: int = 5) -> str:
    return secrets.token_hex(len)


def token():
    return secrets.token_urlsafe(random.randint(100, 300))


def username():
    return hexs(10)


def email():
    name = choice_repeat(string.ascii_lowercase, 16)
    domain = choice_repeat(string.ascii_lowercase, 16)

    return f"{name}@{domain}.com"
