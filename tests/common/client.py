# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

__all__ = ["TestClient"]


def _wrapped_method(method: str):
    async def _method(self, *args, **kwargs):
        kwargs["headers"] = self._inject_auth(kwargs)
        verb = getattr(self.cli, method)
        return await verb(*args, **kwargs)

    _method.__name__ = method
    return _method


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

        do_token = kwargs.get("do_token", True)

        try:
            kwargs.pop("do_token")
        except KeyError:
            pass

        if not do_token:
            return headers

        headers["authorization"] = self.user["token"]
        return headers

    get = _wrapped_method("get")
    post = _wrapped_method("post")
    put = _wrapped_method("put")
    patch = _wrapped_method("patch")
    delete = _wrapped_method("delete")
