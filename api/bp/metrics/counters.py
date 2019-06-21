# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

log = logging.getLogger(__name__)


class MetricsCounters:
    """Simple class to hold counters related to various things of the app."""

    def __init__(self):
        self.data = {
            'request' : 0,
            'response': 0,
            'error': 0,
            'error_ise': 0,
            'file_upload_hour': 0,
            'file_upload_hour_pub': 0,
        }

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
            log.warning('unknown counter: %s', counter)

    async def auto_submit(self, metrics, counter: str):
        await metrics.submit(counter, self.data[counter])
        self.reset_single(counter)
