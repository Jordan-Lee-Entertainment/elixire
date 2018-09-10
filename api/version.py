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

VERSION = '2018.2.7.12'
API_VERSION = '2018.2.4.2'
