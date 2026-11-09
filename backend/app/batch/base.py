from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_JOB_STATES = frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED})


@dataclass(frozen=True)
class JobStatus:
    state: JobState
    progress: float = 0.0  # 0-100
    error: str | None = None


class BatchScheduler(Protocol):
    """What the orchestrator needs from a batch system (AWS Batch, Slurm, k8s Jobs, mock)."""

    async def submit(self, task_id: str, command: str) -> str:
        """Submit a job and return its job id."""
        ...

    async def status(self, job_ids: list[str]) -> dict[str, JobStatus]:
        """Batched status lookup. Unknown ids may be omitted."""
        ...

    async def cancel(self, job_id: str) -> None:
        """Best-effort cancel. No-op for finished or unknown jobs."""
        ...
