# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import json
import asyncio
from typing import Optional, Any, TypeVar, Tuple, List
from collections import defaultdict

from quart import request, send_file as quart_send_file, current_app as app

from api.common import get_user_domain_info, transform_wildcard
from api.enums import FileNameType
from api.permissions import Permissions, domain_permissions
from api.models import Domain

T = TypeVar("T")


def _maybe_type(typ: type, value: Any, default: Optional[T] = None) -> Optional[T]:
    """Tries to convert the given value to the given type.
    Returns None or the value given in the default
    parameter if it fails."""
    # this check is required for mypy to catch that we're
    # checking the value's nullability
    if value is None:
        return default

    try:
        return typ(value)
    except (TypeError, ValueError):
        return default


def int_(val: Optional[Any], default: Optional[int] = None) -> Optional[int]:
    return _maybe_type(int, val, default)


def dict_(val: Optional[Any], default: Optional[dict] = None) -> Optional[dict]:
    return _maybe_type(dict, val, default)


def _semaphore(num):
    """Return a function that when called, returns a new semaphore with the
    given counter."""

    def _wrap():
        return asyncio.Semaphore(num)

    return _wrap


class LockStorage:
    """A storage class to hold locks and semaphores.

    This is a wrapper around a defaultdict so it can hold
    multiple defaultdicts, one for each field declared in _fields.
    """

    _fields = (("delete_files", _semaphore(10)), ("bans", asyncio.Lock))

    def __init__(self):
        self._locks = {}

        for field, typ in self._fields:
            self._locks[field] = defaultdict(typ)

    def __getitem__(self, key):
        return self._locks[key]


def find_different_keys(dict1: dict, dict2: dict) -> list:
    """Find the keys that point to different values in two dicts."""
    keys = []

    for key in dict1:
        if dict1[key] != dict2.get(key):
            keys.append(key)

    return keys


def _get_specified_domain() -> Tuple[Optional[int], Optional[str]]:
    """Return the domain ID and subdomain specified in the current request as a
    query argument, if any.
    """
    try:
        given_domain: Optional[int] = int(request.args["domain"])
    except (KeyError, ValueError):
        given_domain = None

    try:
        given_subdomain = request.args["subdomain"]
    except KeyError:
        given_subdomain = None

    return given_domain, given_subdomain


async def resolve_domain(
    user_id: int, ftype: FileNameType
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """Resolve the domain ID, domain name, and subdomain to be used for an upload.

    This function inspects the current request's query arguments and the user's
    preferred domains and returns the correct information to be used during an
    upload.
    """
    ptype = Permissions.UPLOAD if ftype == FileNameType.FILE else Permissions.SHORTEN

    given_domain, given_subdomain = _get_specified_domain()
    random_domain = bool(request.args.get("random_domain"))

    if given_domain and given_subdomain:
        # If both the domain and subdomain were given, use those.
        domain_id = given_domain
        subdomain_name = given_subdomain
    else:
        # Otherwise, we need to fallback to the user's preferred domain and
        # subdomain.
        user_domain_id, user_subdomain, user_domain = await get_user_domain_info(
            user_id, ftype
        )
        domain_id = given_domain or user_domain_id
        subdomain_name = given_subdomain or user_subdomain

    # TODO: optimize this by using the Domain model (beyond random id fetch)
    #
    # Selecting a random domain overrides domain settings (either via profile OR
    # the query argument).
    if random_domain:
        domain_id = await Domain.fetch_random_id()

    # Check the domain's permissions, which specifies if uploads or shortens are
    # allowed on it.
    await domain_permissions(app, domain_id, ptype)

    # resolve the given (domain_id, subdomain_name) into a usable domain string
    domain_name = await app.db.fetchval(
        """
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """,
        domain_id,
    )

    domain = transform_wildcard(domain_name, subdomain_name)
    return domain_id, domain, subdomain_name


async def send_file(path: str, *, mimetype: Optional[str] = None):
    """Helper function to send files while also supporting Ranged Requests."""
    response = await quart_send_file(path, mimetype=mimetype, conditional=True)

    filebody = response.response
    response.headers["content-length"] = filebody.end - filebody.begin
    response.headers["content-disposition"] = "inline"
    response.headers["content-security-policy"] = "sandbox; frame-src 'None'"

    return response


async def postgres_set_json_codecs(con):
    """Set JSON and JSONB codecs for an asyncpg connection."""
    await con.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )

    await con.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def fetch_json_rows(db, query: str, *args) -> List[Any]:
    """Fetch many rows with JSON/JSONB support."""
    async with db.acquire() as con:
        await postgres_set_json_codecs(con)
        return await con.fetch(query, *args)


def get_ip_addr() -> str:
    """Fetch the IP address for a request.

    Returns the value given in the `REAL_IP_HEADER` header defined in the
    instance configuration file.
    """
    remote_addr = request.remote_addr
    if remote_addr == "<local>":
        remote_addr = "127.0.0.1"

    header = app.econfig.REAL_IP_HEADER
    if header is not None:
        return request.headers.get(header, remote_addr)
    else:
        return remote_addr
