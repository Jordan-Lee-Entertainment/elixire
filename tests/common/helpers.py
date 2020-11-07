# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.bp.datadump.handler import DatadumpQueue
from api.bp.delete import MassDeleteQueue
from api.scheduled_deletes import ScheduledDeleteQueue


def setup_test_app(event_loop, app_) -> None:
    app_._test = True
    app_.loop = event_loop
    app_.econfig.RATELIMITS = {"*": (10000, 1)}
    app_.econfig.CLOUDFLARE = False

    # TODO should we keep this as false?
    app_.econfig.ENABLE_METRICS = False

    # used in internal email/webhook functions for testing
    app_._email_list = []
    app_._webhook_list = []

    # To speedup testing, job queues are set to poll the database faster than
    # their production counterparts.
    DatadumpQueue.poller_seconds = 1
    MassDeleteQueue.poller_seconds = 1
    ScheduledDeleteQueue.poller_seconds = 1
