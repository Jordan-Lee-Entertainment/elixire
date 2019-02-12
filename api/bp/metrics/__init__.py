# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

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
