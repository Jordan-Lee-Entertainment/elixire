# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio

import logging
log = logging.getLogger(__name__)


class JobManager:
    """Manage background jobs."""
    def __init__(self, loop=None):
        log.debug('job manager start')
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = {}

    async def _wrapper(self, job_name, coro):
        try:
            log.debug('running job: %r', job_name)
            await coro
            log.debug('job finish: %r', job_name)

            #: remove itself from the job scheduler
            self.jobs.pop(job_name)
        except asyncio.CancelledError:
            log.warning('cancelled job: %r', job_name)
        except Exception:
            log.exception('Error while running job %r', job_name)

    async def _wrapper_bg(self, job_name, func, args, period: int):
        log.debug('wrapped %r in periodic %dsec',
                  job_name, period)

        try:
            while True:
                log.debug('background tick for %r', job_name)
                await func(*args)
                await asyncio.sleep(period)

            self.jobs.pop(job_name)
        except asyncio.CancelledError:
            log.warning('cancelled job: %r', job_name)
        except Exception:
            log.exception('Error while running job %r', job_name)

    def spawn(self, coro, name: str = None):
        """Spawn a backgrund task once.

        This is meant for relatively short-lived tasks.
        """
        name = name or coro.__name__

        task = self.loop.create_task(
            self._wrapper(name, coro)
        )

        self.jobs[name] = task
        return task

    def spawn_periodic(self, func, args, period: int, name: str = None):
        """Spawn a background task that will be run
        every ``period`` seconds."""
        name = name or func.__name__

        task = self.loop.create_task(
            self._wrapper_bg(name, func, args, period)
        )

        self.jobs[name] = task
        return task

    def exists(self, job_name: str):
        """Return if a given job name exists
        in the job manager."""
        return job_name in self.jobs

    def stop_job(self, job_name: str):
        """Stop a single job."""
        log.debug('stopping job %r', job_name)
        try:
            job = self.jobs.pop(job_name)
            job.cancel()
        except KeyError:
            log.warning('unknown job to cancel: %r', job_name)

    def stop(self):
        """Stop the job manager by
        cancelling all jobs."""
        log.debug('cancelling %d jobs', len(self.jobs))

        for job_name in list(self.jobs.keys()):
            self.stop_job(job_name)
