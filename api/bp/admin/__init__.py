# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from .user import bp as user_bp
from .object import bp as object_bp
from .domain import bp as domain_bp
from .misc import bp as misc_bp

__all__ = ['user_bp', 'object_bp', 'domain_bp', 'misc_bp']
