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

        metrics_limit = getattr(app.econfig, 'METRICS_LIMIT', (100, 3))
        self._timestamps, self._period = metrics_limit

        log.info('starting metrics worker')
        self._worker = loop.create_task(self.worker())

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
        log.info('Unauthenticated InfluxDB connection')
        self.influx = InfluxDBClient(db=cfg.METRICS_DATABASE, loop=self.loop)

    async def _submit(self, datapoint: dict):
        try:
            await self.influx.write(datapoint)
        except Exception:
            log.exception('failed to submit datapoint')

    def _fetch_points(self, limit=None) -> list:
        if limit is None:
            limit = self._timestamps

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

    def _make_tasks(self, points):
        tasks = []
        for point in points:
            task = self.loop.create_task(self._submit(point))
            tasks.append(task)

        return tasks

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

    async def worker(self):
        try:
            while True:
                await self._work()
                await asyncio.sleep(self._period)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception('metrics worker failed')

        log.warning('metrics worker stop')

    def _convert_value(self, value):
        if isinstance(value, int):
            return f'{value}i'
        return f'{value}'

    async def submit(self, title, value):
        """Submit a new datapoint to be sent
        to InfluxDB."""
        if not self.app.econfig.ENABLE_METRICS:
            return

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
