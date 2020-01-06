# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import collections

from .generators import *  # NOQA
from .client import *  # NOQA


Domain = collections.namedtuple("Domain", ["id", "name"])
