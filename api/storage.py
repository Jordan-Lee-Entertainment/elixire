# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
storage.py - multiple routines to fetch things
from redis (as caching) and using postgres as a fallback
"""
import logging
import datetime

from .errors import NotFound

log = logging.getLogger(__name__)


def calc_ttl(dtime: datetime.datetime) -> int:
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
    now = datetime.datetime.utcnow()
    return int((dtime - now).total_seconds())


def check(map_data) -> dict:
    """Check if all values in the map aren't None.

    If one is, returns None.
    """
    # checks if all values in map are not None
    if any(v is None for v in map_data.values()):
        return None

    return map_data


def prefix(user_id: int) -> str:
    """Return the prefix for a key, given user ID."""
    return f"uid:{user_id}"


def solve_domain(domain_name: str, redis=True) -> list:
    """Solve a domain into its Redis keys."""
    k = domain_name.find(".")
    raw_wildcard = f"*.{domain_name}"
    wildcard_name = f"*.{domain_name[k + 1:]}"

    domains = [
        # example: domain_name = elixi.re
        # wildcard_name = *.elixi.re
        # example 2: domain_name = pretty.please-yiff.me
        # wildcard_name = *.please-yiff.me
        raw_wildcard,
        domain_name,
        wildcard_name,
    ]

    if redis:
        return list(map(lambda d: f"domain_id:{d}", domains))

    return domains


class Storage:
    """Storage system.

    This is used by the codebase to provide caching with Redis.
    """

    def __init__(self, app):
        self.app = app
        self.db = app.db
        self.redis = app.redis

    async def get(self, key, typ=str):
        """Get one key from Redis.

        Parameters
        ----------
        key: str
            Key you want to find.
        typ: any
            The type of the value.

        Returns
        -------
        None
            If the key doesn't exist
        False
            If Postgres didn't give anything.
            This serves more as a hint.
        any: typ
            If the key fetching succeeded.
        """
        val = await self.redis.get(key)

        log.debug(f"get {key!r}, type {typ!r}, value {val!r}")
        if typ == bool:
            if val == "True":
                return True
            elif val == "False":
                return False

        # always use "false" to show when the db
        # didnt give us anything
        if val == "false":
            return False

        # key does not exist
        elif val is None:
            return

        return typ(val)

    async def get_multi(self, keys: list, typ=str) -> list:
        """Fetch multiple keys."""
        res = []

        for key in keys:
            val = await self.get(key, typ)
            res.append(val)

        return res

    async def set(self, key, value, **kwargs):
        """Set a key in Redis."""
        key = str(key)

        if isinstance(value, bool):
            value = str(value)

        log.debug(f"set key {key!r} to {value!r}")

        # the string false tells that whatever
        # query the db did returned None.
        value = "false" if value is None else value
        await self.redis.set(key, value, **kwargs)

    async def set_with_ttl(self, key, value, ttl):
        """Set a key and set its TTL afterwards.

        This works better than the expire and pexpire
        keyword arguments in the set() call
        """
        await self.set(key, value)
        await self.redis.expire(key, ttl)

    async def set_multi_one(self, keys: list, value):
        """Set multiple keys to one given value.

        Parameters
        ----------
        keys: List[str]
            List of keys to set.
        value: any
            Value to set for the keys.
        """
        for key in keys:
            await self.set(key, value)

    async def raw_invalidate(self, *keys: tuple):
        """Invalidate/delete a set of keys.

        Parameters
        ----------
        multiple: str
            Any amount of parameters can be given.
            Those represent the keys to be invalidated.
        """
        log.info(f"Invalidating {len(keys)} keys: {keys}")
        await self.redis.delete(*keys)

    async def invalidate(self, user_id: int, *fields: tuple):
        """Invalidate fields given a user id."""
        ukey = prefix(user_id)
        keys = (f"{ukey}:{field}" for field in fields)
        await self.raw_invalidate(*keys)

    async def _generic_1(
        self, key: str, key_type, ttl: int, query: str, *query_args: tuple
    ):
        """Generic storage function for Storage.get_uid
        and Storage.get_username.

        Parameters
        ----------
        key: str
            The key to fetch from Redis.
        key_type: any
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
        val = await self.get(key, key_type)

        if val is False:
            return

        if val is None:
            val = await self.db.fetchval(query, *query_args)
            await self.set_with_ttl(key, val or "false", ttl)

        return val

    async def get_uid(self, username: str) -> int:
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

    async def get_username(self, user_id: int) -> str:
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

    async def actx_username(self, username: str) -> dict:
        """Fetch authentication context important stuff
        given an username.

        The authentication context (actx) is important
        information of the user, only related to authentication
        purposes.

        With that set, actx only contains:
         - username
         - user id
         - password hash

        But doesn't contain anything else in regards to e.g
        user settings.

        Returns
        -------
        dict
        """
        user_id = await self.get_uid(username)
        if not user_id:
            log.warning("user not found")
            return

        actx = await self.actx_userid(user_id)
        if not actx:
            log.warning("actx failed")
            return

        actx.update({"user_id": user_id})
        return check(actx)

    async def actx_userid(self, user_id: str) -> dict:
        """Fetch authentication-related information
        given an user ID.

        More information about the authentication context
        is in Storage.actx_username.

        Returns
        -------
        dict
        """
        ukey = prefix(user_id)

        password_hash = await self.get(f"{ukey}:password_hash")
        active = await self.get(f"{ukey}:active", bool)

        if password_hash is None:
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

        if active is None:
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

        return check(
            {
                "password_hash": password_hash,
                "active": active,
            }
        )

    async def get_fspath(self, shortname: str, domain_id: int) -> str:
        """Get the filesystem path of an image."""
        key = f"fspath:{domain_id}:{shortname}"
        return await self._generic_1(
            key,
            str,
            600,
            """
            SELECT fspath
            FROM files
            WHERE filename = $1
              AND deleted = false
              AND domain = $2
            LIMIT 1
        """,
            shortname,
            domain_id,
        )

    async def get_urlredir(self, filename: str, domain_id: int) -> str:
        """Get a redirection of an URL."""
        key = f"redir:{domain_id}:{filename}"
        return await self._generic_1(
            key,
            str,
            600,
            """
            SELECT redirto
            FROM shortens
            WHERE filename = $1
            AND deleted = false
            AND domain = $2
        """,
            filename,
            domain_id,
        )

    async def get_ipban(self, ip_address: str) -> str:
        """Get the reason for a specific IP ban."""
        key = f"ipban:{ip_address}"
        ban_reason = await self.get(key, str)

        if ban_reason is False:
            return

        if ban_reason is None:
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

    async def get_ban(self, user_id: int) -> str:
        """Get the ban reason for a specific user id."""
        key = f"userban:{user_id}"
        ban_reason = await self.get(key, str)

        if ban_reason is False:
            return

        if ban_reason is None:
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

    async def get_domain_id(self, domain_name: str, err_flag=True) -> int:
        """Get a domain ID, given the domain.

        The old function was common_auth.check_domain and was modified
        so that it could account for our caching.
        """

        keys = solve_domain(domain_name, True)

        for key in keys:
            possible_id = await self.get(key, int)

            # as soon as we get a key that is valid,
            # return it
            if not isinstance(possible_id, bool) and possible_id is not None:
                return possible_id

        # if no keys solve to any domain,
        # query from db and set those keys
        # to the found id

        # This causes some problems since we might
        # set *.re (in the case of domain_name = 'elixi.re') to
        # an actual domain id, but since we use domain_name
        # first, it shouldn't become a problem.

        keys_db = solve_domain(domain_name, False)

        row = await self.db.fetchrow(
            """
        SELECT domain, domain_id
        FROM domains
        WHERE domain = $1
            OR domain = $2
            OR domain = $3
        """,
            *keys_db,
        )

        if row is None:
            # maybe we set only f'domain_id:{domain_name}' to false
            # instead of all 3 keys? dunno
            await self.set_multi_one(keys, "false")

            if err_flag:
                raise NotFound(
                    "This domain does not exist in " "this elixire instance."
                )

            return None

        domain_name, domain_id = row
        await self.set(f"domain_id:{domain_name}", domain_id)
        return domain_id

    async def get_domain_shorten(self, shortname: str) -> int:
        """Get a domain ID for a shorten."""

        return await self.db.fetchval(
            """
        SELECT domain
        FROM shortens
        WHERE filename = $1
        """,
            shortname,
        )

    async def get_domain_file(self, shortname: str) -> int:
        """Get a domain ID for a file."""

        return await self.db.fetchval(
            """
        SELECT domain
        FROM files
        WHERE filename = $1
        """,
            shortname,
        )

    async def get_file_mime(self, shortname: str) -> str:
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
