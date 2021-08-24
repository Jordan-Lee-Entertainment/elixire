# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import math

from api.errors import BadInput


class Pagination:
    """A utility class that helps with pagination."""

    def __init__(self, request):
        self._raw_args = request.raw_args
        self.page = self._int_arg("page")
        self.per_page = self._int_arg("per_page", 20)

        if self.page < 0:
            raise BadInput("Invalid page number")
        if self.per_page < 0:
            raise BadInput("Invalid per_page number")

    def response(self, results, *, total_count):
        """Return the resulting JSON object that the request should return."""
        return {
            "results": results,
            "pagination": {
                "total": math.ceil(total_count / self.per_page),
                "current": self.page,
            },
        }

    def _int_arg(self, name, default=0):
        return int(self._raw_args.get(name, default))
