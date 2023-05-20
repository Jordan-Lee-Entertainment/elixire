# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)


class JobManager:
    """Manage background jobs.

    This manager class does not implement retry logic with error handling.
    """

    # Adding retry logic to this class would require some form of storage in it
    # which would turn it into a dedicated job queue.
    #
    # this codebase is not ready for that yet (see v3 experiments and the
    # violet library), but it is in the roadmap, as email delivery is something
    # we'd want to make more consistent in the error case

    def __init__(self, *, context_function, loop=None):
        log.debug("job manager start")
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = {}
        self.context_creator = context_function

    async def _wrapper_single_shot_task(
        self, function, args: list, kwargs: dict, job_name: str
    ):
        try:
            log.debug("running job: %r", job_name)
            async with self.context_creator():
                await function(*args, **kwargs)
            log.debug("job finish: %r", job_name)
        except asyncio.CancelledError:
            log.warning("cancelled job: %r", job_name)
        except Exception:
            log.exception("Error while running job %r", job_name)
        finally:
            self.jobs.pop(job_name)

    async def _wrapper_periodic(
        self, function, every: int, args: list, kwargs: dict, job_name: str
    ):
        log.debug("wrapped %r in periodic %d seconds", job_name, every)

        try:
            async with self.context_creator():
                while True:
                    log.debug("background tick for %r", job_name)
                    await function(*args, **kwargs)
                    await asyncio.sleep(every)
        except asyncio.CancelledError:
            log.warning("cancelled job: %r", job_name)
        except Exception:
            log.exception("Error while running job %r", job_name)
        finally:
            try:
                self.jobs.pop(job_name)
            except KeyError:
                pass

    def spawn_once(
        self,
        function,
        *,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        name: str = None
    ) -> asyncio.Task:
        """Spawn a background task that runs only once.

        This is meant for short-lived tasks.

        `name` is the GLOBAL name of this task in the job manager. you may
        use it across job runs, but if the job is already running, reusing it
        will raise a ValueError.
        """
        args = args or []
        kwargs = kwargs or {}
        name = name or function.__name__
        if name in self.jobs:
            raise ValueError("Can not spawn two jobs with the same name")

        task = self.loop.create_task(
            self._wrapper_single_shot_task(function, args, kwargs, name)
        )

        self.jobs[name] = task
        return task

    def spawn_periodic(
        self,
        function,
        *,
        every: int,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        name: str = None
    ) -> asyncio.Task:
        """Spawn a background task that will be run periodically.

        `every` represents the amount of seconds waited between "ticks" of
        the given task.

        `name` is the same meaning as spawn().
        """
        args = args or []
        kwargs = kwargs or {}
        name = name or function.__name__
        if name in self.jobs:
            raise ValueError("Can not spawn two jobs with the same name")

        task = self.loop.create_task(
            self._wrapper_periodic(function, every, args, kwargs, name)
        )

        self.jobs[name] = task
        return task

    def exists(self, job_name: str):
        """Return if a given job name exists in the job manager."""
        return job_name in self.jobs

    def stop_job(self, job_name: str):
        """Stop a single job."""
        log.debug("stopping job %r", job_name)
        try:
            job = self.jobs[job_name]
            job.cancel()
        except KeyError:
            log.warning("unknown job to cancel: %r", job_name)
        finally:
            # as a last measure, try to pop() the job
            # post-cancel. if that fails, the job probably
            # already cleaned itself.
            try:
                self.jobs.pop(job_name)
            except KeyError:
                pass

    def stop(self):
        """Call stop_job for all registered jobs."""
        log.debug("cancelling %d jobs", len(self.jobs))

        for job_name in list(self.jobs.keys()):
            self.stop_job(job_name)
