# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

# TODO: add a test so that we don't fall into the overflow regression.

import time

import elixire.tests.creds
from elixire.api.snowflake import _snowflake as time_snowflake, \
    get_snowflake, snowflake_time

async def test_snowflake():
    """Test snowflakes."""
    tstamp = int(time.time() * 1000)
    sflake = time_snowflake(tstamp)
    tstamp2 = snowflake_time(sflake) * 1000

    assert tstamp == tstamp2
