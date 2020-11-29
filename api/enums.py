# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
from enum import Enum


class TokenType:
    """Token type "enum"."""

    NONTIMED = 1
    TIMED = 2


class FileNameType:
    """Represents a type of a filename."""

    FILE = 0
    SHORTEN = 1


class AuthDataType(Enum):
    """Possible authentication methods"""

    PASSWORD = "password"
    TOTP = "totp"
    WEBAUTHN = "webauthn"
