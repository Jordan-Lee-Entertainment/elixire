# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import enum
from typing import List, Any, Union

import logging

from quart.ctx import copy_current_app_context
from .errors import JobExistsError

log = logging.getLogger(__name__)


class FailMode(enum.Enum):
    LogError = 0
    RaiseError = 1
    Retry = 2


def get_failure_mode(kwargs: dict) -> FailMode:
    """Get the wanted failure mode of a background task, given kwargs."""
    fail_mode = kwargs.get("fail_mode", "log_error")
    if isinstance(fail_mode, FailMode):
        return fail_mode

    return {
        "log_error": FailMode.LogError,
        "raise_error": FailMode.RaiseError,
        "retry": FailMode.Retry,
    }[fail_mode]


class JobManager:
    """Manage background jobs."""

    def __init__(self, loop=None):
        log.debug("job manager start")
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = {}

    async def _wrapper(self, job_id: str, func, args: List[Any], **kwargs) -> Any:
        try:
            log.debug("job run: %r", job_id)
            result = await func(args)
            log.debug("job finish: %r", job_id)
            return result
        except asyncio.CancelledError:
            log.warning("job cancelled: %r", job_id)
        except Exception as err:
            failure_mode = get_failure_mode(kwargs)
            if failure_mode == FailMode.RaiseError:
                raise err

            log.exception("job error: %r", job_id)

            if failure_mode == FailMode.Retry:
                retry_time = kwargs.get("retry_time", 5)
                await asyncio.sleep(retry_time)
                await self._wrapper(job_id, func, args, **kwargs)
        finally:
            self.remove_job(job_id)

    async def _wrapper_bg(
        self, job_id: str, func, args: List[Any], period: int, **kwargs
    ):
        async def main_loop():
            while True:
                log.debug("job tick: %r", job_id)
                await func(*args)
                await asyncio.sleep(period)

        log.debug("job start periodic: %r every %ds", job_id, period)
        await self._wrapper(job_id, main_loop, [], **kwargs)

    def _create_task(self, task_id: str, *, main_coroutine):
        if task_id in self.jobs:
            raise JobExistsError(f"Job '{task_id}' already exists")

        task = self.loop.create_task(main_coroutine)
        self.jobs[task_id] = task
        return task

    def spawn(self, func, args, *, task_id: str, **kwargs):
        """Spawn a backgrund task.

        This is meant for one-shot tasks.
        It copies the current app context into the given task.
        """

        @copy_current_app_context
        async def _ctx_wrapper_bg() -> Any:
            return await func(*args)

        # we have two wrappers for the given task:
        #  - one is _ctx_wrapper_bg() to catch and use the current app context
        #  - that runs inside a self._wrapper() that gives basic logging on the
        #     task, handles exceptions, etc.
        return self._create_task(
            task_id,
            main_coroutine=self._wrapper(task_id, _ctx_wrapper_bg, [], **kwargs),
        )

    def spawn_periodic(self, func, args, *, period: int, task_id: str, **kwargs):
        """Spawn a background task that will be run
        every ``period`` seconds."""

        @copy_current_app_context
        async def _ctx_wrapper_bg(*args, **kwargs) -> Any:
            return await self._wrapper_bg(*args, **kwargs)

        return self._create_task(
            task_id,
            main_coroutine=_ctx_wrapper_bg(task_id, func, args, period, **kwargs),
        )

    def exists(self, job_name: str) -> bool:
        """Return if a given job name exists
        in the job manager."""
        return job_name in self.jobs

    def remove_job(self, job_id: str) -> None:
        """Remove a job from the internal jobs dictionary. You most likely want
        to use stop_job()."""
        try:
            self.jobs.pop(job_id)
        except KeyError:
            pass

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
            self.remove_job(job_name)

    def stop(self) -> None:
        """Stop the job manager by cancelling all jobs."""
        log.debug("cancelling %d jobs", len(self.jobs))

        for job_name in list(self.jobs.keys()):
            self.stop_job(job_name)
