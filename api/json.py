# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any
from quart.json import JSONEncoder


class ElixireJSONEncoder(JSONEncoder):
    def encode(self, value: Any):
        # TODO js max int? how do we safely determine a snowflake..
        if isinstance(value, dict) and "id" in value and value["id"] > 10000000:
            value.update({"id": str(value["id"])})

        return super().encode(value)
