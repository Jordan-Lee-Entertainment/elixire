# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any
from quart.json import JSONEncoder

JS_MAX_SAFE_INT = 9007199254740991


def stringify_snowflakes(obj):
    if not isinstance(obj, dict):
        return

    for key, value in obj.items():
        if isinstance(value, dict):
            stringify_snowflakes(value)
            continue

        # TODO how do we safely determine a snowflake..
        if key == "id" and isinstance(value, int) and value > JS_MAX_SAFE_INT:
            obj[key] = str(value)


class ElixireJSONEncoder(JSONEncoder):
    def encode(self, value: Any):
        stringify_snowflakes(value)
        return super().encode(value)
