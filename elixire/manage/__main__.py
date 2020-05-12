#!/usr/bin/env python3
# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import sys

from manage.main import main

import config


def _setup_logging() -> None:
    level = getattr(config, "LOGGING_LEVEL", "INFO")
    logging.basicConfig(level=level)


def run() -> None:
    _setup_logging()
    sys.exit(main(config))


if __name__ == "__main__":
    run()
