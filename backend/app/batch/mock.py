"""In-memory batch scheduler that simulates queueing, concurrency limits, progress and failure.

State advances lazily from the clock on every call, so there is no background thread and tests
can drive it with a fake clock.
"""

import itertools
import math
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.batch.base import TERMINAL_JOB_STATES, JobState, JobStatus

_FAIL_MARKER = re.compile(r"\bfail\b", re.IGNORECASE)
LOST_JOB_ERROR = "job lost: unknown to mock scheduler (was the backend restarted?)"


@dataclass
class _Job:
    id: str
    seq: int
    command: str
    eligible_at: float  # submit time + queue delay
    duration: float  # nominal job length; progress is measured against this
    run_time: float  # how long it actually runs before finishing (or failing)
    will_fail: bool
    state: JobState = JobState.QUEUED
    started_at: float | None = None
    ended_at: float | None = None
    error: str | None = None


class MockBatchScheduler:
    def __init__(
        self,
        *,
        min_duration: float = 5.0,
        max_duration: float = 20.0,
        max_queue_delay: float = 3.0,
        max_concurrent: int = 4,
        failure_rate: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self._min_duration = min_duration
        self._max_duration = max_duration
        self._max_queue_delay = max_queue_delay
        self._max_concurrent = max_concurrent
        self._failure_rate = failure_rate
        self._clock = clock
        self._rng = rng or random.Random()
        self._jobs: dict[str, _Job] = {}
        self._seq = itertools.count()
        self._sim_time = clock()

    # -- BatchScheduler API -------------------------------------------------

    async def submit(self, task_id: str, command: str) -> str:
        self._advance()
        now = self._clock()
        seq = next(self._seq)
        will_fail = bool(_FAIL_MARKER.search(command)) or self._rng.random() < self._failure_rate
        duration = self._rng.uniform(self._min_duration, self._max_duration)
        job = _Job(
            id=f"mock-{seq:06d}-{task_id[:8]}",
            seq=seq,
            command=command,
            eligible_at=now + self._rng.uniform(0, self._max_queue_delay),
            duration=duration,
            # Failing jobs die partway through so the UI shows partial progress.
            run_time=duration * (0.5 if will_fail else 1.0),
            will_fail=will_fail,
        )
        self._jobs[job.id] = job
        return job.id

    async def status(self, job_ids: list[str]) -> dict[str, JobStatus]:
        self._advance()
        now = self._clock()
        out: dict[str, JobStatus] = {}
        for jid in job_ids:
            job = self._jobs.get(jid)
            if job is None:
                out[jid] = JobStatus(JobState.FAILED, 0.0, LOST_JOB_ERROR)
            else:
                out[jid] = JobStatus(job.state, self._progress(job, now), job.error)
        return out

    async def cancel(self, job_id: str) -> None:
        self._advance()
        job = self._jobs.get(job_id)
        if job is None or job.state in TERMINAL_JOB_STATES:
            return
        job.state = JobState.CANCELLED
        job.ended_at = self._clock()
        job.error = "cancelled"

    # -- simulation ---------------------------------------------------------

    def _progress(self, job: _Job, now: float) -> float:
        if job.state == JobState.SUCCEEDED:
            return 100.0
        if job.started_at is None:
            return 0.0
        end = job.ended_at if job.ended_at is not None else now
        pct = (end - job.started_at) / job.duration * 100 if job.duration > 0 else 100.0
        # Failed/cancelled jobs report where they stopped; running jobs never claim 100.
        return round(min(pct, 99.0), 1)

    def _advance(self) -> None:
        """Replay start/finish events up to now, in time order."""
        now = self._clock()
        while True:
            running = [j for j in self._jobs.values() if j.state == JobState.RUNNING]
            queued = [j for j in self._jobs.values() if j.state == JobState.QUEUED]

            next_finish_job = min(running, key=lambda j: j.started_at + j.run_time, default=None)
            next_finish = (
                next_finish_job.started_at + next_finish_job.run_time
                if next_finish_job
                else math.inf
            )

            next_start_job = None
            next_start = math.inf
            if queued and len(running) < self._max_concurrent:
                next_start_job = min(queued, key=lambda j: (j.eligible_at, j.seq))
                next_start = max(next_start_job.eligible_at, self._sim_time)

            t = min(next_finish, next_start)
            if t > now:
                break
            self._sim_time = t

            if next_finish <= next_start:
                job = next_finish_job
                job.ended_at = t
                if job.will_fail:
                    job.state = JobState.FAILED
                    job.error = "mock job failed (exit code 1)"
                else:
                    job.state = JobState.SUCCEEDED
            else:
                next_start_job.state = JobState.RUNNING
                next_start_job.started_at = t

        self._sim_time = max(self._sim_time, now)
