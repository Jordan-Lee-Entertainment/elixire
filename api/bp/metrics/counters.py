# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from aioprometheus import Counter, Gauge, Histogram, Summary

log = logging.getLogger(__name__)


class MetricsCounters:
    """Simple class to hold counters related to various things of the app."""

    def __init__(self):
        self.request = Counter("request", "total requests done")
        self.response = Counter("response", "total responses done")
        self.response_latency = Summary(
            "response_latency", "total time spent on response"
        )
        self.background_latency = Summary(
            "background_latency", "time spent on background processing"
        )

        self.shortname_gen_tries = Summary(
            "object_shortname_gen_tries",
            "amount of times hitting the database to generate a shortname",
        )

        self.data = {}

    def register(self, registry):
        _fields = (
            "request",
            "response",
            "response_latency",
            "background_latency",
            "shortname_gen_tries",
        )

        for field in _fields:
            registry.register(getattr(self, field))

    def reset_all(self):
        """Initialize/reset all counters."""
        for key in self.data:
            self.data[key] = 0

    def reset_single(self, counter):
        """Reset a single counter."""
        self.data[counter] = 0

    def get(self, counter):
        """Get a value for a counter."""
        return self.data[counter]

    def inc(self, counter):
        """Increment a counter by one."""
        try:
            self.data[counter] += 1
        except KeyError:
            log.warning("unknown counter: %s", counter)

    async def auto_submit(self, metrics, counter: str):
        try:
            data = self.data[counter]
        except KeyError:
            log.warning("unknown counter: %s", counter)
            return

        await metrics.submit(counter, data)
        self.reset_single(counter)
