"""
storage.py - multiple routines to fetch things
from redis (as caching) and using postgres as a fallback
"""
import logging

log = logging.getLogger(__name__)


def check(map) -> dict:
    """Check if all values in the map aren't None.

    If one is, returns None.
    """
    # checks if all values in map are not None
    if any(v is None for v in map.values()):
        return None

    return map


def prefix(user_id: int) -> str:
    """Return the prefix for a key, given user ID."""
    return f'uid:{user_id}'


class Storage:
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

        if typ == bool:
            if val == 'True':
                return True
            elif val == 'False':
                return False

        # always use false to show when the db
        # didnt give us anything
        if val == 'false':
            return False

        # key does not exist
        elif val is None:
            return

        return typ(val)

    async def set(self, key, value):
        """Set a key in Redis."""
        with await self.redis as conn:
            if isinstance(value, bool):
                value = str(value)

            log.info(f'setting key {key!r} to {value!r}')
            await conn.set(key, value if value is not None else 'false')

    async def raw_invalidate(self, keys: tuple):
        """Invalidate/delete a set of keys."""
        with await self.redis as conn:
            await conn.delete(*keys)

    async def invalidate(self, user_id: int, *fields: tuple):
        """Invalidate fields given a user id."""
        ukey = prefix(user_id)
        keys = (f'{ukey}:{field}' for field in fields)
        await self.raw_invalidate(keys)

    async def get_uid(self, username: str) -> int:
        """Get an user ID given a username."""
        uid = await self.get(f'uid:{username}', int)

        # db fetching didnt work before
        if uid is False:
            return

        if uid is None:
            uid = await self.db.fetchval("""
            SELECT user_id
            FROM users
            WHERE username=$1
            LIMIT 1
            """, username)

            await self.set(f'uid:{username}', uid)

        return uid

    async def actx_username(self, username: str) -> dict:
        """Fetch authentication context important stuff
        given an username.

        Returns
        -------
        dict
        """
        user_id = await self.get_uid(username)

        actx = await self.actx_userid(user_id)
        if not actx:
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

            await self.set(f'{ukey}:password_hash', password_hash)

        if active is None:
            active = await self.db.fetchval("""
            SELECT active
            FROM users
            WHERE user_id = $1
            """, user_id)

            await self.set(f'{ukey}:active', active)

        return check({
            'password_hash': password_hash,
            'active': active,
        })
