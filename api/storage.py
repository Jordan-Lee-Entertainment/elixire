"""
storage.py - multiple routines to fetch things
from redis (as caching) and using postgres as a fallback
"""
import logging
import datetime

log = logging.getLogger(__name__)
epoch = datetime.datetime.utcfromtimestamp(0)

def unix_time_millis(dt):
    return (dt - epoch).total_seconds() * 1000.0


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
        log.info(f'Getting key {key}, type {typ}')
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

    async def set(self, key, value, **kwargs):
        """Set a key in Redis."""
        with await self.redis as conn:
            if isinstance(value, bool):
                value = str(value)

            log.info(f'setting key {key!r} to {value!r}')
            await conn.set(key, value if value is not None else 'false', **kwargs)

    async def raw_invalidate(self, *keys: tuple):
        """Invalidate/delete a set of keys."""
        log.info(f'Invalidating {len(keys)} keys: {keys}')
        with await self.redis as conn:
            await conn.delete(*keys)

    async def invalidate(self, user_id: int, *fields: tuple):
        """Invalidate fields given a user id."""
        ukey = prefix(user_id)
        keys = (f'{ukey}:{field}' for field in fields)
        await self.raw_invalidate(*keys)

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

    async def get_username(self, user_id: int) -> str:
        """Get a username given user ID."""
        key = f'uname:{user_id}'
        uname = await self.get(key, str)

        if uname is False:
            return

        if uname is None:
            uname = await self.db.fetchval("""
            SELECT username
            FROM users
            WHERE user_id = $1
            LIMIT 1
            """, user_id)

            await self.set(f'uname:{user_id}', uname)

        return uname

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

    async def get_fspath(self, shortname: str, domain_id: int) -> str:
        """Get the filesystem path of an image."""
        key = f'fspath:{domain_id}:{shortname}'
        fspath = await self.get(key, str)

        if fspath is False:
            return

        if fspath is None:
            fspath = await self.db.fetchval("""
            SELECT fspath
            FROM files
            WHERE filename = $1
            AND deleted = false
            AND domain = $2
            LIMIT 1
            """, shortname, domain_id)

            await self.set(key, fspath)

        return fspath

    async def get_urlredir(self, filename: str, domain_id: int) -> str:
        """Get a redirection of an URL."""
        key = f'redir:{domain_id}:{filename}'
        url = await self.get(key, str)

        if url is False:
            return

        if url is None:
            url = await self.db.fetchval("""
            SELECT redirto
            FROM shortens
            WHERE filename = $1
            AND deleted = false
            AND domain = $2
            """, filename, domain_id)

            await self.set(key, url)

        return url

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
            et_millis = int(unix_time_millis(end_timestamp))

            # set key expiration at same time the banning finishes
            await self.set(key, ban_reason, pexpire=et_millis)

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
            et_millis = int(unix_time_millis(end_timestamp))

            # set key expiration at same time the banning finishes
            await self.set(key, ban_reason, pexpire=et_millis)

        return ban_reason
