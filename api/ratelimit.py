"""
Based off discord.py's cooldown code.
"""
import time
import logging

log = logging.getLogger(__name__)


class Ratelimit:
    def __init__(self, requests, second):
        self.requests = int(requests)
        self.second = second

        self._window = 0.0
        self._tokens = self.requests
        self.retries = 0
        self._last = 0.0

    def get_tokens(self, current):
        """Get the current amount of available tokens."""
        if not current:
            current = time.time()

        # by default, use _tokens
        tokens = self._tokens

        # if current timestamp is above _window + seconds
        # reset tokens to self.requests (default)
        if current > self._window + self.second:
            tokens = self.requests

        return tokens

    def update_rate_limit(self):
        """Update current ratelimit state."""
        current = time.time()
        self._last = current
        self._tokens = self.get_tokens(current)

        # we are using the ratelimit for the first time
        # so set current ratelimit window to right now
        if self._tokens == self.requests:
            self._window = current

        # Are we currently ratelimited?
        if self._tokens == 0:
            self.retries += 1
            return self.second - (current - self._window)

        # if not ratelimited, remove a token
        self.retries = 0
        self._tokens -= 1

        # if we got ratelimited after that token removal,
        # set window to now
        if self._tokens == 0:
            self._window = current

    def reset(self):
        """Reset current ratelimit to default state."""
        self._tokens = self.requests
        self._last = 0.0
        self.retries = 0

    def copy(self):
        """Create a copy of this ratelimit.

        Used to manage multiple ratelimits to users.
        """
        return Ratelimit(self.requests, self.second)

    def __repr__(self):
        return (f'<Ratelimit requests{self.requests} second={self.second} '
                f'window: {self._window} tokens={self._tokens}>')


class RatelimitManager:
    def __init__(self, app, ratelimit=None):
        self._cache = {}
        self._cooldown = None

        if ratelimit is None and hasattr(app.econfig, 'RATELIMIT'):
            ratelimit = app.econfig.RATELIMIT
            log.info(f'Loading config ratelimits: {ratelimit!r}')
        else:
            log.info(f'Using given ratelimits: {ratelimit!r}')

        self._cooldown = Ratelimit(**ratelimit)

    def _verify_cache(self):
        current = time.time()
        dead_keys = [k for k, v in self._cache.items()
                     if current > v._last + v.second]
        for k in dead_keys:
            del self._cache[k]

    def get_bucket(self, uid):
        if not self._cooldown:
            return None

        self._verify_cache()

        if uid not in self._cache:
            bucket = self._cooldown.copy()
            self._cache[uid] = bucket
        else:
            bucket = self._cache[uid]

        return bucket
