import datetime
import logging
import asyncio
import time

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

        metrics_limit = getattr(app.econfig, 'METRICS_LIMIT', (100, 3))
        self._timestamps, self._period = metrics_limit

        log.info('starting metrics worker')
        self._worker = loop.create_task(self.worker())

    async def _submit(self, datapoint: dict):
        try:
            await self.app.ifxdb.write(datapoint)
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
