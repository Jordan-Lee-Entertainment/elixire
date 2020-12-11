# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
storage.py - multiple routines to fetch things
from redis (as caching) and using postgres as a fallback
"""

import logging
import datetime
import enum
from ipaddress import IPv4Network, IPv6Network

from typing import Optional, Dict, Union, Any, List, Tuple, Iterable

from api.errors import NotFound

log = logging.getLogger(__name__)

PartialAuthUser = Optional[Dict[str, Union[int, str]]]


def calc_ttl(dtime: datetime.datetime) -> int:
    """Calculate how many seconds remain
    from now to the given timestamp.

    This was made because redis' expireat() function
    was inconsistent.

    Retruns
    -------
    int
        The amount of seconds from now to reach the
        given timestamp.
    """
    now = datetime.datetime.utcnow()
    return int((dtime - now).total_seconds())


def ensure_non_null(map_data: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
    """Check if all values in the map aren't None.

    If one is, returns None.
    """
    # checks if all values in map are not None
    if any(v is None for v in map_data.values()):
        return None

    return map_data


def prefix(user_id: Union[str, int]) -> str:
    """Return the prefix for a key, given user ID."""
    return f"uid:{user_id}"


def object_key(
    prefix: str, domain_id: int, subdomain: Optional[str], shortname: str
) -> str:
    """Make a key for a given object."""
    # protect against people with subdomains of "None"
    subdomain = subdomain or "@none@"
    return f"{prefix}:{domain_id}:{subdomain}:{shortname}"


def solve_domain(domain_name: str, *, redis: bool = False) -> List[str]:
    """Solve a domain into its Redis keys.

    Returns a prefixed namespace when ``redis`` is true.
    """

    # when given a domain, such as b.a.tld, there could be three
    # keys we should check, in order:
    #  *.b.a.tld
    #  b.a.tld
    #  *.a.tld

    domain_as_wildcard = f"*.{domain_name}"

    period_index = domain_name.find(".")
    subdomain_wildcarded = f"*.{domain_name[period_index + 1:]}"

    domains = [domain_as_wildcard, domain_name, subdomain_wildcarded]

    if redis:
        return list(map(lambda d: f"domain_id:{d}", domains))

    return domains


def wanted_network_ranges(
    ipaddress: Union[IPv4Network, IPv6Network]
) -> Iterable[Union[IPv4Network, IPv6Network]]:
    """Get wanted network ranges for a given IPv4 or IPv6 address.

    For IPv4 addresses, we wish to look on the respective /24 prefix as well.
    For IPv6, we wish to look on /64, /48, and /32.
    """

    if isinstance(ipaddress, IPv4Network):
        return (
            ipaddress,
            ipaddress.supernet(new_prefix=24),
        )
    else:
        return (
            ipaddress,
            ipaddress.supernet(new_prefix=64),
            ipaddress.supernet(new_prefix=48),
            ipaddress.supernet(new_prefix=32),
        )


def _get_subdomain(domain: str) -> str:
    """Return the subdomain of a domain.

    Because this function does not notice TLDs, passing "elixi.re" will yield
    "elixi" as the subdomain. So, you must only use this function on domains
    that you are sure have a subdomain.
    """
    try:
        period_index = domain.index(".")
    except ValueError:
        return ""

    return domain[:period_index]


class StorageFlag(enum.Enum):
    """An enum representing how something from :class:`Storage` was resolved."""

    #: The value was found.
    FOUND = 1

    #: The value was not found in Redis, but it might exist in Postgres.
    NOT_CACHED = 2

    #: The value doesn't exist, cached or not.
    NOT_FOUND = 3


class StorageValue:
    """A class representing a value returned by :class:`Storage`."""

    def __init__(self, value: Any, *, flag: StorageFlag = StorageFlag.FOUND) -> None:
        self.flag = flag
        self.value = value

    @property
    def was_found(self) -> bool:
        return self.flag is StorageFlag.FOUND

    @property
    def was_cached(self) -> bool:
        return self.flag is not StorageFlag.NOT_CACHED

    def __bool__(self) -> bool:
        return self.was_found

    def __repr__(self) -> str:
        return f"StorageValue<flag={self.flag!r} value={self.value!r}>"


class Storage:
    """The storage subsystem.

    This class provides an abstraction over the caching with Redis mechanism.

    When storing a given key to Redis, it can be of any value, however,
    internally, the value is *always* casted to a string. This requires type
    checking code that is implemented in :meth:`get` and :meth:`set`.

    A note on the internal storage is that the special sentinel string "false"
    (kept in :prop:`_NOTHING`) represents a cached instance of Postgres not
    returning any rows. (This only applies to non-boolean keys.)
    """

    #: A sentinel value used in Redis as a cached value to signal that Postgres
    #: returned no rows.
    _NOTHING = "false"

    def __init__(self, app):
        self.app = app
        self.db = app.db
        self.redis = app.redis

    def _to_storage_value(self, typ, redis_value: Optional[str]) -> StorageValue:
        if typ == bool:
            if redis_value == "True":
                return StorageValue(True)
            elif redis_value == "False":
                return StorageValue(False)

        # test for the sentinel value that means a cached absence of value
        if redis_value == self._NOTHING:
            return StorageValue(None, flag=StorageFlag.NOT_FOUND)

        # key does not exist in redis, but it might be in postgres
        elif redis_value is None:
            return StorageValue(None, flag=StorageFlag.NOT_CACHED)

        return StorageValue(typ(redis_value), flag=StorageFlag.FOUND)

    async def get(self, key: str, typ: type = str) -> StorageValue:
        """Get a key from Redis.

        Parameters
        ----------
        key:
            Key you want to find.
        typ:
            The type of the value.

        Returns
        -------
        StorageValue
        """
        val = await self.redis.get(key)

        log.debug(f"get {key!r}, type {typ!r}, value {val!r}")
        return self._to_storage_value(typ, val)

    async def multi_get(self, *keys, typ: type = str) -> List[StorageValue]:
        """Fetch multiple keys from Redis.

        This operation involves just a single network operation on Redis, as
        it has the MKEY command.

        All keys should be of the same type.

        Parameters
        ----------
        keys:
            Keys to be fetched.
        typ:
            The type of the value.

        Returns
        -------
        StorageValue
        """
        values = await self.redis.mget(*keys)
        log.debug(f"get {keys!r}, type {typ!r}, value {values!r}")
        return [self._to_storage_value(typ, redis_value) for redis_value in values]

    async def set(self, key: str, value: Optional[Any]) -> None:
        """Set a key in Redis.

        When setting booleans in the cache, they're casted to strings
        internally since Redis only works with strings. However they'll still
        be booleans when you get() them back with typ=bool.

        If value is None, then get() will return
        StorageFlag.PostgresNotFound.
        """

        with await self.redis as conn:
            if isinstance(value, bool):
                value = str(value)

            log.debug(f"set key {key!r} to {value!r}")

            # the string false tells that whatever
            # query the db did returned None.
            value = self._NOTHING if value is None else value
            await conn.set(key, value)

    async def set_with_ttl(
        self, key: str, value: Optional[Any], ttl: int = 600
    ) -> None:
        """Set a key and set its TTL afterwards.

        This works better than the expire and pexpire
        keyword arguments in self.redis.set().
        """
        await self.set(key, value)
        await self.redis.expire(key, ttl)

    async def set_multi_one(self, keys: List[str], value: Optional[Any]) -> None:
        """Set multiple keys to one given value.

        Parameters
        ----------
        keys:
            List of keys to set.
        value:
            Value to set for the keys.
        """
        # TODO mset() exists! we should use it!
        for key in keys:
            await self.set(key, value)

    async def raw_invalidate(self, *keys: Iterable[str]) -> None:
        """Invalidate/delete a set of keys.

        Parameters
        ----------
        multiple: str
            Any amount of parameters can be given.
            Those represent the keys to be invalidated.
        """
        log.info(f"Invalidating {len(keys)} keys: {keys}")
        with await self.redis as conn:
            await conn.delete(*keys)

    async def invalidate(self, user_id: int, *fields: Tuple[str]) -> None:
        """Invalidate fields given a user id."""
        ukey = prefix(user_id)
        keys = (f"{ukey}:{field}" for field in fields)
        await self.raw_invalidate(*keys)

    async def _generic_1(
        self, key: str, key_type: type, ttl: int, query: str, *query_args
    ) -> Optional[Any]:
        """Generic storage function.

        Since many functions in here are based off the same structure:
         - fetch from redis
         - if failure, fetch from db and set on redis
         - return value

        this function was created.

        Parameters
        ----------
        key: str
            The key to fetch from Redis.
        key_type: type
            The key type.
        ttl: int
            The TTL value of the key after setting.
        query: str
            The Postgres query to run if Redis
            does not have the key.
        *query_args: Tuple[any]
            Any arguments to the query.

        Returns
        -------
        None
            When nothing is found on the cache or
            the database.
        any
            Any value that is cached, or found in database.
        """
        storage_value = await self.get(key, key_type)
        value = storage_value.value

        if storage_value.flag is StorageFlag.NOT_FOUND:
            return None

        if storage_value.flag is StorageFlag.NOT_CACHED:
            value = await self.db.fetchval(query, *query_args)
            await self.set_with_ttl(key, value or self._NOTHING, ttl)

        return value

    async def get_uid(self, username: str) -> Optional[int]:
        """Get an user ID given a username."""
        return await self._generic_1(
            f"uid:{username}",
            int,
            600,
            """
            SELECT user_id
            FROM users
            WHERE username = $1
            LIMIT 1
        """,
            username,
        )

    async def get_username(self, user_id: int) -> Optional[str]:
        """Get a username given user ID."""
        return await self._generic_1(
            f"uname:{user_id}",
            str,
            600,
            """
            SELECT username
            FROM users
            WHERE user_id = $1
            LIMIT 1
        """,
            user_id,
        )

    async def auth_user_from_username(self, username: str) -> PartialAuthUser:
        """Fetch a partial user (for authentication purposes), given
        their username.

        Returns
        -------
        PartialAuthUser
            Partial user data containing user id, active field,
            and password hash. may contain username
        """
        user_id = await self.get_uid(username)
        if user_id is None:
            log.warning("user not found")
            return None

        partial = await self.auth_user_from_user_id(user_id)
        if partial is None:
            log.warning("partial user for auth fetch failed")
            return None

        partial.update({"username": username})
        return ensure_non_null(partial)

    async def auth_user_from_user_id(self, user_id: Union[str, int]) -> PartialAuthUser:
        """TODO docstring"""
        ukey = prefix(user_id)

        # this gets and unwraps the value inside of them
        pwd_hash_val = await self.get(f"{ukey}:password_hash")
        password_hash = pwd_hash_val.value

        active_val = await self.get(f"{ukey}:active", bool)
        active = active_val.value

        if not pwd_hash_val.was_found:
            password_hash = await self.db.fetchval(
                """
                SELECT password_hash
                FROM users
                WHERE user_id = $1
                """,
                user_id,
            )

            # keep this cached for 10 minutes
            await self.set_with_ttl(f"{ukey}:password_hash", password_hash, 600)

        if not active_val.was_found:
            active = await self.db.fetchval(
                """
                SELECT active
                FROM users
                WHERE user_id = $1
                """,
                user_id,
            )

            # keep this cached as well
            await self.set_with_ttl(f"{ukey}:active", active, 600)

        return ensure_non_null(
            {"user_id": user_id, "password_hash": password_hash, "active": active}
        )

    async def get_fspath(
        self, *, shortname: str, domain_id: int, subdomain: Optional[str] = None
    ) -> StorageValue:
        """Get the path to an uploaded file by its shortname, domain ID, and
        optional subdomain (empty string means root, None means any subdomain).
        """

        # NOTE keep in mind get_fspath and get_urlredir must be in sync.
        key = object_key("fspath", domain_id, subdomain, shortname)

        storage_value = await self.get(key, str)

        if storage_value.was_cached:
            return storage_value

        query = """
            SELECT fspath
            FROM files
            WHERE filename = $1
              AND deleted = false
              AND domain = $2
        """

        # i'd say this is a pretty ugly way to synthetize the query
        # since when we don't have a subdomain we shouldn't do any searches
        # on it to start with.
        args = []
        if subdomain is not None:
            query += "AND subdomain = $3"
            args.append(subdomain)
        else:
            query += "AND subdomain IS NULL"

        query += " LIMIT 1"

        value = await self.db.fetchval(query, shortname, domain_id, *args)
        await self.set_with_ttl(key, value or self._NOTHING, 600)

        flag = StorageFlag.NOT_FOUND if value is None else StorageFlag.FOUND
        return StorageValue(value, flag=flag)

    async def get_urlredir(
        self, shortname: str, domain_id: int, subdomain: Optional[str] = None
    ) -> StorageValue:
        """Get a redirection of an URL."""
        # NOTE copied from get_fspath()
        key = object_key("redir", domain_id, subdomain, shortname)
        storage_value = await self.get(key, str)

        if storage_value.was_cached:
            return storage_value

        query = """
            SELECT redirto
            FROM shortens
            WHERE filename = $1
            AND deleted = false
            AND domain = $2
        """

        # i'd say this is a pretty ugly way to synthetize the query
        # since when we don't have a subdomain we shouldn't do any searches
        # on it to start with.
        args = []
        if subdomain is not None:
            query += "AND subdomain = $3"
            args.append(subdomain)
        else:
            query += "AND subdomain IS NULL"

        query += " LIMIT 1"

        value = await self.db.fetchval(query, shortname, domain_id, *args)
        await self.set_with_ttl(key, value or self._NOTHING, 600)

        flag = StorageFlag.NOT_FOUND if value is None else StorageFlag.FOUND
        return StorageValue(value, flag=flag)

    async def get_ipban(
        self, ip_address: Union[IPv4Network, IPv6Network]
    ) -> Optional[str]:
        """Get the reason for a specific IP ban."""
        wanted_addresses = wanted_network_ranges(ip_address)

        # create MKEY query
        wanted_cache_keys = [f"ipban:{inet}" for inet in wanted_addresses]
        results = await self.multi_get(*wanted_cache_keys)

        # possible ban reasons for any of the ranges is inside results
        #
        # for each result:
        # if nothing found for that result, skip
        # if that result was not found in redis (NOT_CACHED), query the db to
        #     find out, cache the result, return if the result was found
        # if was found in cache, return
        #
        # if none of the keys returned by now, then the ip is good

        for inet, cache_key, result in zip(
            wanted_addresses, wanted_cache_keys, results
        ):
            if result.flag is StorageFlag.NOT_FOUND:
                continue

            if result.flag is StorageFlag.FOUND:
                return result.value

            if result.flag is StorageFlag.NOT_CACHED:
                row = await self.db.fetchrow(
                    """
                    SELECT ip_address, reason, end_timestamp
                    FROM ip_bans
                    WHERE $1 << ip_address AND end_timestamp > now()
                    ORDER BY ip_address DESC
                    LIMIT 1
                    """,
                    inet,
                )

                if row is None:
                    # a ttl is optional here, because we already invalidate
                    # when we ban/unban a certain address
                    await self.set_with_ttl(cache_key, self._NOTHING, 300)
                    continue
                else:
                    # we have found something that *might* be what we want, but
                    # can be at a larger inet range, so we cache that instead of
                    # the address we were querying
                    found_inet, reason, end_timestamp = (
                        row["ip_address"],
                        row["reason"],
                        row["end_timestamp"],
                    )

                    found_cache_key = f"ipban:{found_inet}"

                    # set key expiration at same time the banning finishes
                    await self.set_with_ttl(
                        found_cache_key, reason, calc_ttl(end_timestamp)
                    )

                    return reason

        return None

    async def get_ban(self, user_id: int) -> Optional[str]:
        """Get the ban reason for a specific user id."""
        key = f"userban:{user_id}"
        ban_reason_val = await self.get(key, str)
        ban_reason = ban_reason_val.value

        if ban_reason_val.flag is StorageFlag.NOT_FOUND:
            return None

        if ban_reason_val.flag is StorageFlag.NOT_CACHED:
            row = await self.db.fetchrow(
                """
            SELECT reason, end_timestamp
            FROM bans
            WHERE user_id = $1 AND end_timestamp > now()
            LIMIT 1
            """,
                user_id,
            )

            if row is None:
                await self.set(key, None)
                return None

            ban_reason = row["reason"]
            end_timestamp = row["end_timestamp"]

            # set key expiration at same time the banning finishes
            await self.set(key, ban_reason)
            await self.redis.expire(key, calc_ttl(end_timestamp))

        return ban_reason

    async def get_domain_id(
        self, given_domain: str, *, raise_notfound: bool = True
    ) -> Optional[Tuple[int, str]]:
        """Get a tuple containing the domain ID and the subdomain, given the
        full domain of a given request.

        Raises NotFound by default.
        """

        def _subdomain_valid(subdomain: str, domain: str) -> str:
            return subdomain if domain.startswith("*.") else ""

        # now we need to solve the domain.
        #
        # the `solve_domain` function returns a list of all of the possible
        # domain names that could be in the database that matches up to the host
        # that the user typed. it's necessary to resolve ambiguities.
        #
        # for example, if a user navigated to a.elixi.re, there are 3 possible
        # domains that that could be referring to:
        #
        #   1) *.a.elixi.re (the root of the wildcard domain)
        #   2) a.elixi.re   (a plain domain on a subdomain)
        #   3) *.elixi.re   (a subdomain of a wildcard domain)
        #
        # (not necessarily returned in that order.)
        possibilities = solve_domain(given_domain)
        assert len(possibilities) == 3

        subdomain = _get_subdomain(given_domain)

        # check for cached mappings from domain to domain id
        for possible_domain in possibilities:
            possible_id = await self.get(f"domain_id:{possible_domain}", int)

            # return as soon as we get a valid domain id
            if possible_id.was_found:
                return possible_id.value, _subdomain_valid(subdomain, possible_domain)

        # if no cached mappings were found, query the db for each possibility
        # and cache the result of the real domain that the host resolves to.

        resolved_domain = await self.db.fetchrow(
            """
            SELECT domain, domain_id
            FROM domains
            WHERE domain = $1
                OR domain = $2
                OR domain = $3
            """,
            *possibilities,
        )

        # an actual domain wasn't found from the possibilities
        if resolved_domain is None:
            # cache all of the possible domains as not existing
            await self.set_multi_one(
                [f"domain_id:{possible_domain}" for possible_domain in possibilities],
                self._NOTHING,
            )

            if raise_notfound:
                raise NotFound("This domain does not exist in this elixire instance.")

            return None

        # map the actual domain name to the domain_id in cache
        domain_name, domain_id = resolved_domain
        await self.set(f"domain_id:{domain_name}", domain_id)

        return domain_id, _subdomain_valid(subdomain, domain_name)

    async def get_domain_shorten(
        self, shortname: str
    ) -> Optional[Tuple[int, Optional[str]]]:
        """Get a domain ID for a shorten."""
        return await self.db.fetchrow(
            """
            SELECT domain, subdomain
            FROM shortens
            WHERE filename = $1
            """,
            shortname,
        )

    async def get_domain_file(
        self, shortname: str
    ) -> Optional[Tuple[int, Optional[str]]]:
        """Get a tuple of domain id and subdomain for a file."""
        return await self.db.fetchrow(
            """
            SELECT domain, subdomain
            FROM files
            WHERE filename = $1
            """,
            shortname,
        )

    async def get_file_mime(self, shortname: str) -> Optional[str]:
        """Get the File's mimetype stored on the database."""

        key = f"mime:{shortname}"
        return await self._generic_1(
            key,
            str,
            600,
            """
            SELECT mimetype
            FROM files
            WHERE filename = $1
              AND deleted = false
            LIMIT 1
            """,
            shortname,
        )
