#!/usr/bin/env python3
# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio
import sys

from manage.main import amain

import config


def _setup_logging():
    level = getattr(config, "LOGGING_LEVEL", "INFO")
    logging.basicConfig(level=level)


if __name__ == "__main__":
    _setup_logging()

    loop = asyncio.get_event_loop()
    status = loop.run_until_complete(amain(loop, config, sys.argv))

    sys.exit(status)
