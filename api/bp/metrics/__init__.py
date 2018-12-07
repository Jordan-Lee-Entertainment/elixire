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
elixire - metrics system

This sets up various basic metrics for the instance.

Since it would be complicated to store then in Postgres
all by themselves (and Postgres wouldn't be the proper
solution to that), all metrics are published to InfluxDB.

In production, you should use Grafana to visualize the data,
or anything that connects with InfluxDB, really.
"""
__all__ = ['bp', 'is_consenting']

from .blueprint import bp, is_consenting
