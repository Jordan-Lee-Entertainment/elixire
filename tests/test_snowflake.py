# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import time

from api.snowflake import (
    _snowflake as time_snowflake,
    get_snowflake, snowflake_time
)


def test_snowflake_simple():
    """Simple snowflake typing test"""
    sflake = get_snowflake()
    assert isinstance(sflake, int)
    assert isinstance(snowflake_time(sflake), float)


def test_snowflake_guarantee():
    """Test if a given snowflake gives the correct timestamp."""
    tstamp = int(time.time() * 1000)
    sflake = time_snowflake(tstamp)
    tstamp2 = snowflake_time(sflake) * 1000

    assert tstamp == tstamp2

def test_sflake_overflow():
    """Ensure snowflake library doesn't fall on a regression after
    generating ~4096 snowflakes."""
    last_id = get_snowflake()

    for _ in range(4097):
        new_id = get_snowflake()

        # the difference between last_id and new_id can't be too great.
        # thats how the bug happens.

        delta = new_id - last_id

        if delta > 100000000:
            raise RuntimeError('delta too great')

        # update last_id to keep up
        last_id = new_id
