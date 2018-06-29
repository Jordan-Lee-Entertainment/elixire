#!/usr/bin/env python3.6
import logging

from manage.main import main

import config

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    main(config)
