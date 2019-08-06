# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
storage.py - multiple routines to fetch things
from redis (as caching) and using postgres as a fallback
"""

import logging
import datetime
import enum

from typing import Optional, Dict, Union, Any, List, Tuple, Iterable

from api.errors import NotFound

log = logging.getLogger(__name__)

PartialAuthUser = Optional[Dict[str, Union[int, str]]]


def calc_ttl(dtime: datetime.datetime) -> float:
    """Calculate how many seconds remain
    from now to the given timestamp.

    This was made because redis' expireat() function
    was inconsistent.

    Retruns
    -------
    float
        The amount of seconds from now to reach the
        given timestamp.
    """
    now = datetime.datetime.now()
    return (dtime - now).total_seconds()


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


def _get_subdomain(domain: str) -> Optional[str]:
    """Return the subdomain of a domain.

    Because this function does not notice TLDs, passing "elixi.re" will yield
    "elixi" as the subdomain. So, you must only use this function on domains
    that you are sure have a subdomain.
    """
    try:
        period_index = domain.index(".")
    except ValueError:
        return None

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
        if typ == bool:
            if val == "True":
                return StorageValue(True)
            elif val == "False":
                return StorageValue(False)

        # test for the sentinel value that means a cached absence of value
        if val == self._NOTHING:
            return StorageValue(None, flag=StorageFlag.NOT_FOUND)

        # key does not exist in redis, but it might be in postgres
        elif val is None:
            return StorageValue(None, flag=StorageFlag.NOT_CACHED)

        return StorageValue(typ(val), flag=StorageFlag.FOUND)

    async def get_multi(self, keys: List[str], typ: type = str) -> List[StorageValue]:
        """Fetch multiple keys."""
        res = []

        for key in keys:
            val = await self.get(key, typ)
            res.append(val)

        return res

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

    async def set_with_ttl(self, key: str, value: Optional[Any], ttl: int) -> None:
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
        self, shortname: str, domain_id: int, subdomain: Optional[str] = None
    ) -> StorageValue:
        """Get the filesystem path of an image."""
        key = f"fspath:{domain_id}:{subdomain}:{shortname}"

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
        key = f"redir:{domain_id}:{subdomain}:{shortname}"
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

    async def get_ipban(self, ip_address: str) -> Optional[str]:
        """Get the reason for a specific IP ban."""
        key = f"ipban:{ip_address}"
        ban_reason_val = await self.get(key, str)
        ban_reason = ban_reason_val.value

        if ban_reason_val.flag is StorageFlag.NOT_FOUND:
            return None

        if ban_reason_val.flag is StorageFlag.NOT_CACHED:
            row = await self.db.fetchrow(
                """
                SELECT reason, end_timestamp
                FROM ip_bans
                WHERE ip_address = $1 AND end_timestamp > now()
                LIMIT 1
                """,
                ip_address,
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
    ) -> Optional[Tuple[int, Optional[str]]]:
        """Get a tuple containing the domain ID and the subdomain, given the
        full domain of a given request.

        Raises NotFound by default.
        """

        keys = solve_domain(given_domain)
        assert len(keys) == 3

        subdomain = _get_subdomain(given_domain)

        for key in keys:
            possible_id = await self.get(f"domain_id:{key}", int)

            # as soon as we get a key that is valid,
            # return it
            if (
                not isinstance(possible_id, bool)
                and possible_id.flag is StorageFlag.FOUND
            ):
                return possible_id.value, _subdomain_valid(subdomain, key)

        # if no keys solve to any domain,
        # query from db and set those keys
        # to the found id

        # This causes some problems since we might
        # set *.re (in the case of domain_name = 'elixi.re') to
        # an actual domain id, but since we use domain_name
        # first, it shouldn't become a problem.

        row = await self.db.fetchrow(
            """
            SELECT domain, domain_id
            FROM domains
            WHERE domain = $1
                OR domain = $2
                OR domain = $3
            """,
            *keys,
        )

        if row is None:
            await self.set_multi_one(keys, self._NOTHING)
            if raise_notfound:
                raise NotFound("This domain does not exist in this elixire instance.")

            return None

        domain_name, domain_id = row
        await self.set(f"domain_id:{domain_name}", domain_id)
        return domain_id, _subdomain_valid(subdomain, domain_name)

    async def get_domain_shorten(self, shortname: str) -> Optional[int]:
        """Get a domain ID for a shorten."""
        return await self.db.fetchval(
            """
            SELECT domain
            FROM shortens
            WHERE filename = $1
            """,
            shortname,
        )

    async def get_domain_file(self, shortname: str) -> Optional[int]:
        """Get a domain ID for a file."""
        return await self.db.fetchval(
            """
            SELECT domain
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
