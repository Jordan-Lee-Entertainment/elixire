# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import re
import urllib.parse


def extract_first_url(string: str) -> urllib.parse.ParseResult:
    urls = re.findall(r"(https?://\S+)", string)
    if not urls:
        raise ValueError("Expected URLs in string")

    return urllib.parse.urlparse(urls[0])


def password_auth_object(username: str, password: str):
    return {
        "username": username,
        "authdata_type": "password",
        "authdata": {"password": password},
    }
