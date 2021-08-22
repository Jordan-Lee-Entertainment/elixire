# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - error classes
"""


class APIError(Exception):
    """General API Error"""

    status_code = 500

    def get_payload(self):
        return {}


class BadInput(APIError):
    """Bad input from the user."""

    status_code = 400

    def get_payload(self):
        try:
            return self.args[1]
        except IndexError:
            return {}


class FailedAuth(APIError):
    """Failed to authenticate."""

    status_code = 403


class NotFound(APIError):
    """Resource not found"""

    status_code = 404


class Ratelimited(APIError):
    """Too many requests to the application."""

    status_code = 429

    def get_payload(self):
        return {
            "retry_after": self.args[1],
        }


class Banned(APIError):
    """To be thrown by the ratelimiting handler.

    Banned error handlers should disable the user on sight.
    """

    status_code = 420

    def get_payload(self):
        return {"reason": self.args[0]}


class FeatureDisabled(APIError):
    """When a feature is explicitly disabled in config"""

    status_code = 503


# upload specific errors
class BadImage(APIError):
    """Wrong image mimetype."""

    status_code = 415


class BadUpload(APIError):
    """Upload precondition failed"""

    status_code = 412


class QuotaExploded(APIError):
    """When your quota is exploded or will be exploded."""

    status_code = 469
