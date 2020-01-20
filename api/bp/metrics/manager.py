# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import time

from aioinflux import InfluxDBClient

log = logging.getLogger(__name__)


# from https://stackoverflow.com/a/312464
def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i : i + n]


class MetricsManager:
    """Manager class for metric-related functions.

    This class manages the metric queue and makes sure the
    backend won't spam the receiving InfluxDB server.
    """

    def __init__(self, app, loop):
        self.app = app
        self.loop = loop

        #: all datapoints to be sent
        self.points = {}

        #: InfluxDB connection
        self.influx = None

        self._start_influx()

        # make sure we default to a sane ratelimit
        metrics_limit = getattr(app.econfig, "METRICS_LIMIT", (100, 3))
        self._timestamps, self._period = metrics_limit

        log.info("starting metrics worker")

        if app.econfig.ENABLE_METRICS:
            self.app.sched.spawn_periodic(
                self._work, [], period=self._period, name="metrics_worker"
            )

    def _start_influx(self):
        cfg = self.app.econfig

        if not cfg.ENABLE_METRICS:
            log.info("Metrics are disabled")
            return

        database = cfg.METRICS_DATABASE

        if cfg.INFLUXDB_AUTH:
            host, port = cfg.INFLUX_HOST

            log.info("Authenticated InfluxDB connection")

            # authenticate with given credentials and SSL (if any)
            self.influx = InfluxDBClient(
                db=database,
                host=host,
                port=port,
                ssl=cfg.INFLUX_SSL,
                username=cfg.INFLUX_USER,
                password=cfg.INFLUX_PASSWORD,
                loop=self.loop,
            )

            return

        # default mode is unauthenticated influx connection
        # at localhost.
        log.warning("Unauthenticated InfluxDB connection")
        self.influx = InfluxDBClient(db=cfg.METRICS_DATABASE, loop=self.loop)

    def _fetch_points(self, limit=None) -> list:
        """Fetch datapoints to properly send to InfluxDB."""
        if limit is None:
            limit = self._timestamps

        # sort timestamps from oldest to youngest
        timestamps = sorted(self.points.keys())

        if limit != 0:
            timestamps = timestamps[: self._timestamps]

        log.debug(f"{len(timestamps)} datapoints found...")

        # fetch the respective points, in the order they were put in.
        points = []
        for tstamp in timestamps:
            try:
                point = self.points.pop(tstamp)
                points.append(point)
            except ValueError:
                pass

        return points

    async def _work(self):
        # if there aren't any datapoints to
        # submit, do nothing
        if not self.points:
            log.debug("no points")
            return

        points = self._fetch_points()
        all_points = "\n".join(points)
        try:
            await self.influx.write(all_points)
        except Exception as err:
            log.warning(f"failed to submit datapoint: {err!r}")

        del points
        del all_points

    def _convert_value(self, value):
        if isinstance(value, int):
            return f"{value}i"

        return f"{value}"

    async def submit(self, title, value):
        """Submit a new datapoint to be sent
        to InfluxDB."""
        if not self.app.econfig.ENABLE_METRICS:
            return

        #: this is relative to the app, NOT
        #  to be dispatched to InfluxDB.
        timestamp = str(time.monotonic())

        # line format uses a nanosecond timestamp, so
        # we generate one from time.time().
        current = time.time()

        # extract all precision we can, then convert to int
        current = int(current * (10 ** 6))

        # then raise it to how many missing orders
        # of magnitude to get a nanosecond timestamp
        current = current * (10 ** 3)

        value_converted = self._convert_value(value)
        self.points[timestamp] = f"{title} value={value_converted} {current}"

    async def _close(self):
        if self.influx:
            log.info("closing influxdb conn")
            await self.influx.close()

    async def finish_all(self):
        """Finish all remaining datapoints"""
        if not self.points:
            log.warning("no points to finish")
            await self._close()
            return

        points = self._fetch_points(0)
        full_str = "\n".join(points)
        try:
            await self.influx.write(full_str)
        except Exception as err:
            log.warning(f"failed to submit datapoint: {err!r}")

        await self._close()

    async def stop(self):
        """Stop the manager by cancelling
        its worker task and finishing any
        remaining datapoints."""
        self.app.sched.stop("metrics_worker")
        await self.finish_all()
