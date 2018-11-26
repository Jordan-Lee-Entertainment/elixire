import asyncio

import logging
log = logging.getLogger(__name__)


class JobManager:
    """Manage background jobs."""
    def __init__(self, loop=None):
        log.debug('job manager start')
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = []

    async def _wrapper(self, coro):
        job_name = coro.__name__

        try:
            log.debug('running job: %r', job_name)
            await coro
        except Exception:
            log.exception('Error while running job %r', job_name)
        except asyncio.CancelledError:
            log.warning('cancelled job: %r', job_name)

    async def _wrapper_bg(self, func, args, period: int):
        job_name = func.__name__

        log.debug('wrapped %r in periodic %dsec',
                  job_name, period)

        try:
            while True:
                log.debug('background tick for %r', job_name)
                await func(*args)
                await asyncio.sleep(period)
        except Exception:
            log.exception('Error while running job %r', job_name)
        except asyncio.CancelledError:
            log.warning('cancelled job: %r', job_name)

    def spawn(self, coro):
        """Spawn a backgrund task once."""
        task = self.loop.create_task(
            self._wrapper(coro)
        )

        self.jobs.append(task)

    def spawn_periodic(self, func, args, period: int):
        """Spawn a background task that will
        be run every ``period`` seconds."""
        task = self.loop.create_task(
            self._wrapper_bg(func, args, period)
        )

        self.jobs.append(task)

    def stop(self):
        """Stop the job manager by
        cancelling all jobs."""
        log.debug('cancelling %d jobs', len(self.jobs))

        for job in self.jobs:
            job.cancel()
