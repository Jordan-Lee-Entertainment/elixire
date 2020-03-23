# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
from typing import TypeVar, List, Optional

from winter import get_snowflake

from api.models import Domain, User, Shorten
from api.common.user import delete_user
from api.common.profile import gen_user_shortname

from tests.common.generators import hexs

__all__ = ["TestClient"]


def _wrapped_method(method: str):
    async def _method(self, *args, **kwargs):
        kwargs["headers"] = self._inject_auth(kwargs)
        verb = getattr(self.cli, method)
        return await verb(*args, **kwargs)

    _method.__name__ = method
    return _method


T = TypeVar("T")


class TestClient:
    """Test client that wraps quart's TestClient and a test
    user and adds authorization headers to test requests."""

    def __init__(self, test_cli, test_user):
        self.cli = test_cli
        self.app = test_cli.app
        self.user = test_user
        self._resources: List[T] = []

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
    head = _wrapped_method("head")

    async def _create_resource(self, _classmethod, *args, **kwargs):
        async with self.app.app_context():
            resource = await _classmethod(*args, **kwargs)

        self._resources.append(resource)
        return resource

    def add_resource(self, resource) -> None:
        self._resources.append(resource)

    async def create_domain(self, domain_str: Optional[str] = None) -> Domain:
        domain_str = domain_str or f"*.test-{hexs(10)}.test"
        return await self._create_resource(Domain.create, domain_str)

    async def create_shorten(
        self,
        redirto: Optional[str] = None,
        user_id: Optional[int] = None,
        domain_id: Optional[int] = None,
        subdomain: Optional[str] = None,
    ) -> Shorten:
        redirto = redirto or "https://example.test"
        user_id = user_id or self.user["user_id"]
        domain_id = domain_id or 0
        subdomain = subdomain or ""

        shorten_id = get_snowflake()
        async with self.app.app_context():
            shortname, _ = await gen_user_shortname(user_id, table="shortens")

        await self.app.db.execute(
            """
            INSERT INTO shortens (shorten_id, filename,
                uploader, redirto, domain, subdomain)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            shorten_id,
            shortname,
            user_id,
            redirto,
            domain_id,
            subdomain,
        )

        async with self.app.app_context():
            shorten = await Shorten.fetch(shorten_id)

        assert shorten is not None
        self._resources.append(shorten)
        return shorten

    async def cleanup(self):
        """Delete all allocated test resources."""
        for resource in self._resources:
            async with self.app.app_context():
                if isinstance(resource, User):
                    task = await delete_user(resource.id, delete=True)
                    await asyncio.shield(task)
                else:
                    await resource.delete()
