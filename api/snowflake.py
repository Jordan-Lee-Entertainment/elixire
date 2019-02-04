# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
snowflake.py - snowflake helper functions

    These functions generate discord-like snowflakes.
    File brought in from
        litecord-reference(https://github.com/lnmds/litecord-reference)
"""
import time
import hashlib
import os
import base64

# encoded in ms
EPOCH = 1420070400000

# internal state
_generated_ids = 0
PROCESS_ID = 1
WORKER_ID = 1

Snowflake = int


def get_invite_code() -> str:
    """Get a random invite code."""
    random_stuff = hashlib.sha512(os.urandom(1024)).digest()
    code = base64.urlsafe_b64encode(random_stuff).decode().replace('=', '5') \
        .replace('_', 'W').replace('-', 'm')
    return code[:6]


def _snowflake(timestamp: int) -> Snowflake:
    """Get a snowflake from a specific timestamp

    This function relies on modifying internal variables
    to generate unique snowflakes. Because of that every call
    to this function will generate a different snowflake,
    even with the same timestamp.

    Arguments
    ---------
    timestamp: int
        Timestamp to be feed in to the snowflake algorithm.
        This timestamp has to be an UNIX timestamp
         with millisecond precision.
    """
    # Yes, using global variables aren't the best idea
    global _generated_ids
    epochized = timestamp - EPOCH

    # 22 bits to insert the other variables
    sflake = epochized << 22

    sflake |= (WORKER_ID % 32) << 17
    sflake |= (PROCESS_ID % 32) << 12
    sflake |= (_generated_ids % 4096)

    _generated_ids += 1

    return sflake


def snowflake_time(snowflake: Snowflake) -> float:
    """Get the UNIX timestamp(with millisecond precision, as a float)
    from a specific snowflake.
    """
    # bits 22 and onward encode epochized
    epochized = snowflake >> 22

    # since epochized is the time *since* the EPOCH
    # the unix timestamp will be the time *plus* the EPOCH
    timestamp = epochized + EPOCH

    # convert it to seconds
    # since we don't want to break the entire
    # snowflake interface
    return timestamp / 1000


def get_snowflake():
    """Generate a snowflake"""
    return _snowflake(int(time.time() * 1000))
