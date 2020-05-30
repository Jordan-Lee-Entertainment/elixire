# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import math
from typing import Tuple, Union

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


def lazy_paginate() -> Tuple[int, int, int]:
    """Main function for lazy pagination, where there aren't specific pages
    a route wishes to serve, but it provides before/after semantics.

    It returns a 3-int tuple, where the client's before/after/limit parameters
    are.

    The range for the limit parameter is from 1 to 100.

    The default value for before is the biggest 64-bit integer.
    The default value for after is 0.
    The default value for limit is 100.
    """
    before = request.args.get("before")
    if before is None:
        # NOTE the biggest value in int64 is this
        before = (1 << 63) - 1
    else:
        try:
            before = int(before)
        except ValueError:
            raise BadInput("Optional before parameter must be an integer")

    try:
        after = int(request.args.get("after") or 0)
    except ValueError:
        raise BadInput("Optional after parameter must be an integer")

    try:
        limit = int(request.args.get("limit") or 100)
        limit = max(1, limit)
        limit = min(100, limit)
    except ValueError:
        limit = 100

    return before, after, limit
