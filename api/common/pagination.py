# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import math

from typing import List, Any

from quart import request

from api.errors import BadInput


class Pagination:
    """A utility class that helps with pagination."""

    def __init__(self):
        self._args = request.args
        self.page = self._int_arg("page")
        self.per_page = self._int_arg("per_page", 20)

        if self.page < 0:
            raise BadInput("Invalid page number")
        if self.per_page < 0:
            raise BadInput("Invalid per_page number")

    def response(self, results: List[Any], *, total_count: int):
        """Return the resulting JSON object that the request should return."""
        return {
            "results": results,
            "pagination": {
                "total": math.ceil(total_count / self.per_page),
                "current": self.page,
            },
        }

    def _int_arg(self, name: str, default: int = 0) -> int:
        return int(self._args.get(name, default))
