#!/usr/bin/env python3
# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
import sys

from manage.main import amain

import config


def _setup_logging():
    level = getattr(config, "LOGGING_LEVEL", "INFO")
    logging.basicConfig(level=level)


if __name__ == "__main__":
    _setup_logging()
    loop = asyncio.get_event_loop()
    _, exitcode = loop.run_until_complete(amain(loop, config, sys.argv[1:]))
    sys.exit(exitcode)
