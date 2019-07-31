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


def token():
    return secrets.token_urlsafe(random.randint(100, 300))


def username():
    return secrets.token_hex(random.randint(5, 13))


def email():
    name = choice_repeat(string.ascii_lowercase, 16)
    domain = choice_repeat(string.ascii_lowercase, 16)

    return f"{name}@{domain}.com"


async def login_normal(test_cli) -> str:
    resp = await test_cli.post(
        "/api/login", json={"user": USERNAME, "password": PASSWORD}
    )

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)

    return data["token"]


async def login_admin(test_cli) -> str:
    resp = await test_cli.post(
        "/api/login", json={"user": ADMIN_USER, "password": ADMIN_PASSWORD}
    )

    assert resp.status_code == 200
    data = await resp.json
    assert isinstance(data, dict)

    return data["token"]


class TestClient:
    """Test client that wraps quart's TestClient and a test
    user and adds authorization headers to test requests."""

    def __init__(self, test_cli, test_user):
        self.cli = test_cli
        self.app = test_cli.app
        self.user = test_user

    def __getitem__(self, key):
        return self.user[key]

    def _inject_auth(self, kwargs: dict) -> list:
        """Inject the test user's API key into the test request before
        passing the request on to the underlying TestClient."""
        headers = kwargs.get("headers", {})
        headers["authorization"] = self.user["token"]
        return headers

    async def get(self, *args, **kwargs):
        """Send a GET request."""
        kwargs["headers"] = self._inject_auth(kwargs)
        return await self.cli.get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        """Send a POST request."""
        kwargs["headers"] = self._inject_auth(kwargs)
        return await self.cli.post(*args, **kwargs)

    async def put(self, *args, **kwargs):
        """Send a POST request."""
        kwargs["headers"] = self._inject_auth(kwargs)
        return await self.cli.put(*args, **kwargs)

    async def patch(self, *args, **kwargs):
        """Send a PATCH request."""
        kwargs["headers"] = self._inject_auth(kwargs)
        return await self.cli.patch(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        """Send a DELETE request."""
        kwargs["headers"] = self._inject_auth(kwargs)
        return await self.cli.delete(*args, **kwargs)
