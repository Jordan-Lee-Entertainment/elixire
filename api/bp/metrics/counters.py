# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging
from aioprometheus import Counter, Gauge

log = logging.getLogger(__name__)


class MetricsCounters:
    """Simple class to hold counters related to various things of the app."""

    def __init__(self):
        self.request = Counter("request", "total requests done")
        self.response = Counter("response", "total responses done")
        self.errors = Counter("error", "total errors returned")
        self.errors_ise = Counter("error_ise", "total non-api errors returned")

        self.file_upload = Gauge("file_uploads_total", "total files being uploaded")
        self.file_upload_pub = Gauge(
            "file_uploads_total_pub",
            "total files being uploaded (only users who consented)",
        )

        self.data = {}

    def register(self, registry):
        _fields = (
            "request",
            "response",
            "errors",
            "errors_ise",
            "file_upload",
            "file_upload_pub",
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
