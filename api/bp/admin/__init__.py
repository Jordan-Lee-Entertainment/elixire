# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from .user import bp as user_bp
from .object import bp as object_bp
from .domain import bp as domain_bp
from .misc import bp as misc_bp
from .settings import bp as settings_bp
from .bans import bp as bans_bp
from .violet_jobs import bp as violet_jobs_bp

__all__ = [
    "user_bp",
    "object_bp",
    "domain_bp",
    "misc_bp",
    "settings_bp",
    "bans_bp",
    "violet_jobs_bp",
]
