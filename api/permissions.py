# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - domain permission helper
"""
from .errors import BadInput, FeatureDisabled


# TODO make Permissions a bitflag, or something?
class Permissions:
    """Hold bit positions for each permission."""

    SHORTEN = 0
    UPLOAD = 1


async def domain_permissions(domain, permission: int, raise_on_err=True) -> bool:
    flag = domain.permissions & (1 << permission)

    if (not flag) and raise_on_err:
        raise FeatureDisabled(f"This domain has perm {permission} disabled")

    return bool(flag)
