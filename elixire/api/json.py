# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Any
from quart.json import JSONEncoder
from winter import EPOCH
from hail import Flake


def stringify_snowflakes(obj):
    if not isinstance(obj, dict):
        return

    for key, value in obj.items():
        if isinstance(value, dict):
            stringify_snowflakes(value)
            continue

        if key == "id" and isinstance(value, int) and value > EPOCH:
            obj[key] = str(value)


class ElixireJSONEncoder(JSONEncoder):
    def default(self, value: Any):
        if isinstance(value, Flake):
            return str(value)

        return super().default(value)

    def encode(self, value: Any):
        stringify_snowflakes(value)
        return super().encode(value)
