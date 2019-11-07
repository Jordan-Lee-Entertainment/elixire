# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
from typing import List, Any, Optional

import logging

from quart.ctx import copy_current_app_context

log = logging.getLogger(__name__)


class JobManager:
    """Manage background jobs."""

    def __init__(self, loop=None):
        log.debug("job manager start")
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = {}

    async def _wrapper(self, job_name: str, coro, **kwargs: bool) -> Any:
        """Wrapper for spawn()."""
        try:
            log.debug("running job: %r", job_name)
            result = await coro
            log.debug("job finish: %r", job_name)
            return result
        except asyncio.CancelledError:
            log.warning("cancelled job: %r", job_name)
        except Exception as err:
            if kwargs.get("raise_underlying_error", False):
                raise err
            else:
                log.exception("Error while running job %r", job_name)
        finally:
            self.jobs.pop(job_name)

    async def _wrapper_bg(self, job_name: str, func, args: List[Any], period: int):
        """Wrapper for spawn_periodic()."""
        log.debug("wrapped %r in periodic %dsec", job_name, period)

        try:
            while True:
                log.debug("background tick for %r", job_name)
                await func(*args)
                await asyncio.sleep(period)
        except asyncio.CancelledError:
            log.warning("cancelled job: %r", job_name)
        except Exception:
            log.exception("Error while running job %r", job_name)
        finally:
            try:
                self.jobs.pop(job_name)
            except KeyError:
                pass

    def _create_task(self, *, task_id: str, main_coroutine):
        if task_id in self.jobs:
            raise ValueError(f"Task '{task_id}' already exists")

        task = self.loop.create_task(main_coroutine)
        self.jobs[task_id] = task
        return task

    def spawn(self, coro, *, task_id: str, **kwargs):
        """Spawn a backgrund task.

        This is meant for one-shot tasks.
        It copies the current app context into the given task.

        If you wish to catch the coroutine's exception instead of quieting it,
        you must assign the raise_underlying_error kwarg to true.
        """

        @copy_current_app_context
        async def _ctx_wrapper_bg() -> Any:
            return await coro

        # we have two wrappers for the given task:
        #  - one is _ctx_wrapper_bg() to catch and use the current app context
        #  - that runs inside a self._wrapper() that gives basic logging on the
        #     task, handles exceptions, etc.
        return self._create_task(
            task_id=task_id,
            main_coroutine=self._wrapper(task_id, _ctx_wrapper_bg(), **kwargs),
        )

    def spawn_periodic(self, func, args, *, period: int, task_id: str):
        """Spawn a background task that will be run
        every ``period`` seconds."""

        @copy_current_app_context
        async def _ctx_wrapper_bg(*args, **kwargs) -> Any:
            return await self._wrapper_bg(*args, **kwargs)

        return self._create_task(
            task_id=task_id, main_coroutine=_ctx_wrapper_bg(task_id, func, args, period)
        )

    def exists(self, job_name: str) -> bool:
        """Return if a given job name exists
        in the job manager."""
        return job_name in self.jobs

    def stop_job(self, job_name: str) -> None:
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

    def stop(self) -> None:
        """Stop the job manager by cancelling all jobs."""
        log.debug("cancelling %d jobs", len(self.jobs))

        for job_name in list(self.jobs.keys()):
            self.stop_job(job_name)
