# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from .ban import setup as ban
from .files import setup as files
from .find import setup as find
from .user import setup as user
from .migration import setup as migration
from .domains import setup as domains

__all__ = ["ban", "files", "find", "user", "migration", "domains"]
