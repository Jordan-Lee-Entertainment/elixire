# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import re
import asyncio
import urllib.parse


def extract_first_url(string: str) -> urllib.parse.ParseResult:
    url = re.search(r"(https?://\S+)", string)
    if not url:
        raise ValueError("Expected URLs in string")

    return urllib.parse.urlparse(url.group(0))


async def extract_url_from_emails(app, old_email_count) -> urllib.parse.ParseResult:
    """Wait for a little while expecting an email to appear for tests."""

    current_attempt = 0
    while True:
        if current_attempt > 10:
            raise AssertionError("Timed out waiting for email")

        if len(app._test_email_list) > old_email_count:
            break

        await asyncio.sleep(0.3)
        current_attempt += 1

    return extract_first_url(app._test_email_list[-1]["body"])
