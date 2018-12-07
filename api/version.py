"""
elixire
Copyright (C) 2018  elixi.re Team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

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

VERSION = '2018.2.9.8'
API_VERSION = '2018.2.4.5'
