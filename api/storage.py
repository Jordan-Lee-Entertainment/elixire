"""
storage.py - multiple routines to fetch things
from redis (as caching) and using postgres as a fallback
"""
import logging
import datetime

from .errors import NotFound

log = logging.getLogger(__name__)


def unix_time(dt: datetime.datetime) -> int:
    """Convert a datetime object to a UNIX timestamp.

    Returns
    -------
    int
        The UNIX timestamp of the datetime object.
    """
    epoch = datetime.datetime.utcfromtimestamp(0)
    return (dt - epoch).total_seconds()


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
    return f'uid:{user_id}'


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
        with await self.redis as conn:
            val = await conn.get(key)

        log.info(f'get {key!r}, type {typ!r}, value {val!r}')
        if typ == bool:
            if val == 'True':
                return True
            elif val == 'False':
                return False

        # always use "false" to show when the db
        # didnt give us anything
        if val == 'false':
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

        with await self.redis as conn:
            if isinstance(value, bool):
                value = str(value)

            log.info(f'Setting key {key!r} to {value!r}')

            # the string false tells that whatever
            # query the db did returned None.
            await conn.set(key, value or 'false', **kwargs)

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
        log.info(f'Invalidating {len(keys)} keys: {keys}')
        with await self.redis as conn:
            await conn.delete(*keys)

    async def invalidate(self, user_id: int, *fields: tuple):
        """Invalidate fields given a user id."""
        ukey = prefix(user_id)
        keys = (f'{ukey}:{field}' for field in fields)
        await self.raw_invalidate(*keys)

    async def _generic_1(self, key: str, key_type,
                         query: str, *query_args: tuple):
        """Generic storage function for Storage.get_uid
        and Storage.get_username.

        Parameters
        ----------
        key: str
            The key to fetch from Redis.
        key_type: any
            The key type.
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

            await self.set(key, val or 'false')

        return val

    async def get_uid(self, username: str) -> int:
        """Get an user ID given a username."""
        return await self._generic_1(f'uid:{username}', int, """
            SELECT user_id
            FROM users
            WHERE username = $1
            LIMIT 1
        """, username)

    async def get_username(self, user_id: int) -> str:
        """Get a username given user ID."""
        return await self._generic_1(f'uname:{user_id}', str, """
            SELECT username
            FROM users
            WHERE user_id = $1
            LIMIT 1
        """, user_id)

    async def actx_username(self, username: str) -> dict:
        """Fetch authentication context important stuff
        given an username.

        Returns
        -------
        dict
        """
        user_id = await self.get_uid(username)
        if not user_id:
            log.info('user not found')
            return

        actx = await self.actx_userid(user_id)
        if not actx:
            log.info('actx failed')
            return

        actx.update({'user_id': user_id})
        return check(actx)

    async def actx_userid(self, user_id: str) -> dict:
        """Fetch authentication-related information
        given an user ID.

        Returns
        -------
        dict
        """
        ukey = prefix(user_id)

        password_hash = await self.get(f'{ukey}:password_hash')
        active = await self.get(f'{ukey}:active', bool)

        if password_hash is None:
            password_hash = await self.db.fetchval("""
            SELECT password_hash
            FROM users
            WHERE user_id = $1
            """, user_id)

            await self.set(f'{ukey}:password_hash', password_hash or 'false')

        if active is None:
            active = await self.db.fetchval("""
            SELECT active
            FROM users
            WHERE user_id = $1
            """, user_id)

            await self.set(f'{ukey}:active', active or 'false')

        return check({
            'password_hash': password_hash,
            'active': active,
        })

    async def get_fspath(self, shortname: str, domain_id: int) -> str:
        """Get the filesystem path of an image."""
        key = f'fspath:{domain_id}:{shortname}'
        return await self._generic_1(key, str, """
            SELECT fspath
            FROM files
            WHERE filename = $1
              AND deleted = false
              AND domain = $2
            LIMIT 1
        """, shortname, domain_id)

    async def get_urlredir(self, filename: str, domain_id: int) -> str:
        """Get a redirection of an URL."""
        key = f'redir:{domain_id}:{filename}'
        return await self._generic_1(key, str, """
            SELECT redirto
            FROM shortens
            WHERE filename = $1
            AND deleted = false
            AND domain = $2
        """, filename, domain_id)

    async def get_ipban(self, ip_address: str) -> str:
        """Get the reason for a specific IP ban."""
        key = f'ipban:{ip_address}'
        ban_reason = await self.get(key, str)

        if ban_reason is False:
            return

        if ban_reason is None:
            row = await self.db.fetchrow("""
            SELECT reason, end_timestamp
            FROM ip_bans
            WHERE ip_address = $1 AND end_timestamp > now()
            LIMIT 1
            """, ip_address)

            if row is None:
                await self.set(key, None)
                return None

            ban_reason = row['reason']
            end_timestamp = row['end_timestamp']

            # set key expiration at same time the banning finishes
            await self.set(key, ban_reason)
            await self.redis.expireat(key, unix_time(end_timestamp))

        return ban_reason

    async def get_ban(self, user_id: int) -> str:
        """Get the ban reason for a specific user id."""
        key = f'userban:{user_id}'
        ban_reason = await self.get(key, str)

        if ban_reason is False:
            return

        if ban_reason is None:
            row = await self.db.fetchrow("""
            SELECT reason, end_timestamp
            FROM bans
            WHERE user_id = $1 AND end_timestamp > now()
            LIMIT 1
            """, user_id)

            if row is None:
                await self.set(key, None)
                return None

            ban_reason = row['reason']
            end_timestamp = row['end_timestamp']

            # set key expiration at same time the banning finishes
            await self.set(key, ban_reason)
            await self.redis.expireat(key, unix_time(end_timestamp))

        return ban_reason

    async def get_domain_id(self, domain_name: str, err_flag=True) -> int:
        """Get a domain ID, given the domain.

        The old function was common_auth.check_domain and was modified
        so that it could account for our caching.
        """
        # hacky but it works
        _sp = domain_name.split('.')[0] + '.'
        subdomain_name = domain_name.replace(_sp, "*.")
        wildcard_name = f'*.{domain_name}'

        keys = [
            # example, domain_name = elixi.re
            # subdomain_name = *.re
            # wildcard_name = *.elixi.re
            f'domain_id:{domain_name}',
            f'domain_id:{subdomain_name}',
            f'domain_id:{wildcard_name}',
        ]

        possible_ids = await self.get_multi(keys, int)

        try:
            return next(possible for possible in possible_ids
                        if not isinstance(possible, bool) and possible is not None)
        except StopIteration:
            # fetch from db
            domain_id = await self.db.fetchval("""
            SELECT domain_id
            FROM domains
            WHERE domain = $1
               OR domain = $2
               OR domain = $3
            """, domain_name, subdomain_name, wildcard_name)

            if domain_id is None:
                await self.set_multi_one(keys, 'false')
                if err_flag:
                    raise NotFound('This domain does not exist in this elixire instance.')
                return None

            await self.set_multi_one(keys, domain_id)
            return domain_id
