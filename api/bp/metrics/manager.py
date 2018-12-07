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

import logging
import asyncio
import time

from aioinflux import InfluxDBClient

log = logging.getLogger(__name__)


# from https://stackoverflow.com/a/312464
def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


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
        metrics_limit = getattr(app.econfig, 'METRICS_LIMIT', (100, 3))
        self._timestamps, self._period = metrics_limit

        log.info('starting metrics worker')

        self.app.sched.spawn_periodic(
            self._work, [], self._period,
            'metrics_worker'
        )

    def _start_influx(self):
        cfg = self.app.econfig

        if not cfg.ENABLE_METRICS:
            log.info('Metrics are disabled')
            return

        database = cfg.METRICS_DATABASE

        if cfg.INFLUXDB_AUTH:
            host, port = cfg.INFLUX_HOST

            log.info('Authenticated InfluxDB connection')

            # authenticate with given credentials and SSL (if any)
            self.influx = InfluxDBClient(
                db=database, host=host, port=port,
                ssl=cfg.INFLUX_SSL,
                username=cfg.INFLUX_USER,
                password=cfg.INFLUX_PASSWORD,
                loop=self.loop,
            )

            return

        # default mode is unauthenticated influx connection
        # at localhost.
        log.warning('Unauthenticated InfluxDB connection')
        self.influx = InfluxDBClient(db=cfg.METRICS_DATABASE, loop=self.loop)

    async def _submit(self, datapoint: dict):
        try:
            await self.influx.write(datapoint)
        except Exception as err:
            log.warning(f'failed to submit datapoint: {err!r}')

    def _fetch_points(self, limit=None) -> list:
        """Fetch datapoints to properly send to InfluxDB."""
        if limit is None:
            limit = self._timestamps

        # sort timestamps from oldest to youngest
        timestamps = sorted(self.points.keys())

        if limit != 0:
            timestamps = timestamps[:self._timestamps]

        log.debug(f'{len(timestamps)} datapoints found...')

        # fetch the respective points, in the order they were put in.
        points = []
        for tstamp in timestamps:
            try:
                point = self.points.pop(tstamp)
                points.append(point)
            except ValueError:
                pass

        return points

    def _make_tasks(self, points: list):
        """Make the proper _submit tasks, given a set of datapoints."""
        # for each datapoint, spawn a _submit coroutine and its
        # respective task wrapping it.
        return list(map(
            lambda x: self.loop.create_task(self._submit(x)),
            points
        ))

    async def _work(self):
        # if there aren't any datapoints to
        # submit, do nothing
        if not self.points:
            log.debug('no points')
            return

        points = self._fetch_points()
        tasks = self._make_tasks(points)

        # send the points to the server
        done, pending = await asyncio.wait(tasks)
        log.debug(f'{len(done)} done {len(pending)} pending')

    def _convert_value(self, value):
        if isinstance(value, int):
            return f'{value}i'

        return f'{value}'

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
        self.points[timestamp] = f'{title} value={value_converted} {current}'

    async def finish_all(self):
        """Finish all remaining datapoints"""
        if not self.points:
            log.warning('no points to finish')
            return

        points = self._fetch_points(0)
        for chunk in chunks(points, self._timestamps):
            log.info(f'finish_all: finishing on {len(chunk)} points')

            tasks = self._make_tasks(points)
            done, pending = await asyncio.wait(tasks)

            log.info(f'finish_all: {len(done)} done {len(pending)} pending')

            await asyncio.sleep(self._period)

        if self.influx:
            log.info('closing influxdb conn')
            await self.influx.close()

    async def stop(self):
        """Stop the manager by cancelling
        its worker task and finishing any
        remaining datapoints."""
        self.app.sched.stop_job('metrics_worker')
        await self.finish_all()
