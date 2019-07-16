# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
api/version.py

This file describes our versioning scheme and current versions
for the Backend and API.

Since the Backand and API are separate pieces of thought (e.g
changes in fspath don't apply as an API change, as fspaths
are never brought publicly on the API), we version them
separately.

We use the current year of development + SemVer 2.0.0. so our versions look as:
    YEAR.MAJOR.MINOR.REV

Notes to keep:
 - YEAR changes do not apply to semver's MAJOR.
"""

VERSION = '2019.2.11.3'
API_VERSION = '2019.2.4.8'
