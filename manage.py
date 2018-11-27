#!/usr/bin/env python3
import logging
import sys

from manage.main import main

import config

def _setup_logging():
    level = getattr(config, 'LOGGING_LEVEL', 'INFO')
    logging.basicConfig(level=level)

if __name__ == '__main__':
    _setup_logging()
    sys.exit(main(config))
