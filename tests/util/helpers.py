# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import re
import urllib.parse


def extract_first_url(string: str) -> urllib.parse.ParseResult:
    url = re.search(r"(https?://\S+)", string)
    if not url:
        raise ValueError("Expected URLs in string")

    return urllib.parse.urlparse(url.group(0))
