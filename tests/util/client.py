# elixire: Image Host software
# Copyright 2018-2022, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.common.auth import gen_token

__all__ = ["TestClientWithUser"]


def _wrapped_method(method: str):
    async def _method(self, *args, **kwargs):
        kwargs["headers"] = self._inject_auth(kwargs)
        verb = getattr(self.cli, method)
        return await verb(*args, **kwargs)

    _method.__name__ = method
    return _method


class TestClientWithUser:
    """A class that acts as an overlay between tests and the
    underlying TestClient, automatically injecting authentication headers."""

    def __init__(self, test_cli, test_user):
        self.cli = test_cli
        self.app = test_cli.app
        self.user = test_user
        self.must_reset_user = False

    def must_reset(self):
        """Signal the test client that the given user must be reset as the
        test might have changed some important state for it."""
        self.must_reset_user = True

    async def cleanup(self):
        if self.user is not None and self.must_reset_user:
            await self._reset_user()

    @property
    def id(self):
        return self.user["user_id"]

    @property
    def password(self):
        return self.user["password"]

    @property
    def username(self):
        return self.user["username"]

    @property
    def email(self):
        return self.user["email"]

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
    head = _wrapped_method("head")

    async def _reset_user(self):
        assert self.user is not None
        user_id = self.user["user_id"]

        row = await self.app.db.fetchrow(
            """
            UPDATE users
                SET active = true
            WHERE
                user_id = $1
            RETURNING
                username, password_hash
            """,
            user_id,
        )
        username = row["username"]
        self.user["username"] = username
        self.user["password_hash"] = row["password_hash"]

        # regen token
        async with self.app.app_context():
            self.user["token"] = gen_token(self.user)

        await self.app.db.execute(
            """
            UPDATE limits
            SET
                blimit = DEFAULT,
                shlimit = DEFAULT
            WHERE user_id  = $1
            """,
            user_id,
        )

        await self.app.redis.delete(f"uid:{username}")
        await self.app.redis.delete(f"uid:{user_id}:active")
        await self.app.redis.delete(f"uid:{user_id}:password_hash")
        await self.app.redis.delete(f"userban:{user_id}")
