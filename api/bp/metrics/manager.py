import datetime
import logging
import asyncio
import time

from aioinflux import InfluxDBClient

log = logging.getLogger(__name__)


class MetricsManager:
    """Manager class for metric-related functions.

    This class manages the metric queue and makes sure the
    backend won't spam the receiving InfluxDB server.
    """
    def __init__(self, app, loop):
        self.app = app

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
            )

            return

        # default mode is unauthenticated influx connection
        # at localhost.
        log.info('Unauthenticated InfluxDB connection')
        self.influx = InfluxDBClient(db=cfg.METRICS_DATABASE)

    async def _submit(self, datapoint: dict):
        try:
            await self.influx.write(datapoint)
        except Exception:
            log.exception('failed to submit datapoint')

    async def _work(self):
        # if there aren't any datapoints to
        # submit, do nothing
        if not self.points:
            log.debug('no points')
            return

        # fetch lowest timestamps first
        timestamps = sorted(self.points.keys())[:self._timestamps]
        log.debug(f'{len(timestamps)} keys found, sending')
        points = []

        # fetch respective points to send,
        # deleting them from the queue
        for tstamp in timestamps:
            try:
                point = self.points.pop(tstamp)
                points.append(point)
            except ValueError:
                pass

        tasks = []
        for point in points:
            tasks.append(self._submit(point))

        # send the points to the server
        await asyncio.wait(tasks)
        log.debug('Waited succesfully!')

    async def worker(self):
        try:
            while True:
                await self._work()
                await asyncio.sleep(self._period)
        except Exception:
            log.exception('metrics worker failed')

        log.warning('metrics worker stop')

    async def submit(self, title, value):
        """Submit a new datapoint to be sent
        to InfluxDB."""
        if not self.app.econfig.ENABLE_METRICS:
            return

        timestamp = time.monotonic()
        self.points[timestamp] = {
            'time': datetime.datetime.utcnow(),
            'measurement': title,
            'fields': {
                'value': value,
            }
        }
