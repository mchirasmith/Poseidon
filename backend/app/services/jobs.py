"""In-memory background job registry for reconstruction runs."""
from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable


class Busy(Exception):
    """Raised when the concurrent job limit is reached."""


@dataclass
class Job:
    id: str
    state: str = "running"  # running | done | error
    stage: str | None = None
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    message: str | None = None

    @property
    def elapsed_ms(self) -> int:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return int((end - self.started_at) * 1000)


class JobRegistry:
    """Single-process job registry; running jobs execute via asyncio.to_thread."""

    def __init__(self, max_jobs: int, ttl_seconds: int):
        self._jobs: dict[str, Job] = {}
        self._max_jobs = max_jobs
        self._ttl_seconds = ttl_seconds
        self._tasks: set[asyncio.Task] = set()

    def _evict_stale(self) -> None:
        now = time.monotonic()
        stale = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at is not None and now - job.finished_at > self._ttl_seconds
        ]
        for job_id in stale:
            del self._jobs[job_id]

    def _running_count(self) -> int:
        return sum(1 for job in self._jobs.values() if job.state == "running")

    def get(self, job_id: str) -> Job | None:
        self._evict_stale()
        return self._jobs.get(job_id)

    async def start(self, fn: Callable[[Callable[[str], None]], None]) -> Job:
        self._evict_stale()
        if self._running_count() >= self._max_jobs:
            raise Busy("too many concurrent jobs")

        job = Job(id=str(uuid.uuid4()))
        self._jobs[job.id] = job

        def set_stage(name: str) -> None:
            job.stage = name

        async def runner() -> None:
            try:
                await asyncio.to_thread(fn, set_stage)
                job.state = "done"
            except Exception:
                job.state = "error"
                job.message = "reconstruction failed"
                traceback.print_exc()
            finally:
                job.finished_at = time.monotonic()

        task = asyncio.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job
