# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from ..mock import MockAuditLog  # noqa: E402


def setup_test_app(event_loop, app_) -> None:
    app_._test = True
    app_.loop = event_loop
    app_.econfig.RATELIMITS = {"*": (10000, 1)}

    # TODO should we keep this as false?
    app_.econfig.ENABLE_METRICS = False

    # use mock instances of some external services.
    app_.audit_log = MockAuditLog()

    # used in internal email/webhook functions for testing
    app_._email_list = []
    app_._webhook_list = []
