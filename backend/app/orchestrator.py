"""Advances workflow state. The only writer of task/workflow status besides cancel.

Every tick re-derives what to do from the DB, so the loop is idempotent and a restart resumes
where it left off.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app import dag
from app.batch import BatchScheduler, JobState, JobStatus
from app.models import (
    ACTIVE_WORKFLOW_STATUSES,
    IN_FLIGHT_TASK_STATUSES,
    TERMINAL_TASK_STATUSES,
    Task,
    TaskStatus,
    Workflow,
    WorkflowStatus,
    utcnow,
)

log = logging.getLogger(__name__)

_JOB_TO_TASK = {
    JobState.SUCCEEDED: TaskStatus.SUCCEEDED,
    JobState.FAILED: TaskStatus.FAILED,
    JobState.CANCELLED: TaskStatus.CANCELLED,
}


class Orchestrator:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        scheduler: BatchScheduler,
        *,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._session_factory = session_factory
        self.scheduler = scheduler
        self._now = now
        # Serialises tick() and cancel() so a cancel can't be overwritten by an in-progress tick.
        self._lock = asyncio.Lock()

    async def run_forever(self, interval: float) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("orchestrator tick failed")
            await asyncio.sleep(interval)

    async def tick(self) -> None:
        async with self._lock:
            with self._session_factory() as session:
                workflow_ids = session.scalars(
                    select(Workflow.id).where(Workflow.status.in_(ACTIVE_WORKFLOW_STATUSES))
                ).all()
                for wf_id in workflow_ids:
                    wf = session.get(Workflow, wf_id, options=[selectinload(Workflow.tasks)])
                    try:
                        await self._advance(session, wf)
                        session.commit()
                    except Exception:
                        session.rollback()
                        log.exception("failed to advance workflow %s", wf_id)

    async def cancel(self, workflow_id: str) -> Workflow | None:
        """Cancel in-flight jobs and mark every unfinished task CANCELLED."""
        async with self._lock:
            with self._session_factory() as session:
                wf = session.get(Workflow, workflow_id, options=[selectinload(Workflow.tasks)])
                if wf is None:
                    return None
                if wf.status not in ACTIVE_WORKFLOW_STATUSES:
                    return wf
                now = self._now()
                for task in wf.tasks:
                    if task.status in IN_FLIGHT_TASK_STATUSES and task.batch_job_id:
                        try:
                            await self.scheduler.cancel(task.batch_job_id)
                        except Exception:
                            log.exception("failed to cancel job %s", task.batch_job_id)
                    if task.status not in TERMINAL_TASK_STATUSES:
                        task.status = TaskStatus.CANCELLED
                        task.finished_at = now
                wf.status = WorkflowStatus.CANCELLED
                wf.finished_at = now
                session.commit()
                return wf

    # -- internals ----------------------------------------------------------

    async def _advance(self, session: Session, wf: Workflow) -> None:
        now = self._now()

        # 1. Sync in-flight tasks from the batch scheduler.
        in_flight = [t for t in wf.tasks if t.status in IN_FLIGHT_TASK_STATUSES]
        if in_flight:
            statuses = await self.scheduler.status([t.batch_job_id for t in in_flight])
            for task in in_flight:
                job = statuses.get(task.batch_job_id) or JobStatus(
                    JobState.FAILED, task.progress, "job not found in batch scheduler"
                )
                _apply_job_status(task, job, now)

        # 2. Anything downstream of a failed/cancelled task can never run.
        tasks_by_name = {t.name: t for t in wf.tasks}
        for task in wf.tasks:
            if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                for name in dag.downstream_of(task.name, wf.tasks):
                    child = tasks_by_name[name]
                    if child.status == TaskStatus.PENDING:
                        child.status = TaskStatus.SKIPPED
                        child.error = f"upstream task '{task.name}' did not succeed"
                        child.finished_at = now

        # 3. Submit tasks whose dependencies have all succeeded. Commit after each submit so a
        #    later failure can't roll back a job id we've already handed to the batch system.
        for task in dag.ready_tasks(wf.tasks):
            task.batch_job_id = await self.scheduler.submit(task.id, task.command)
            task.status = TaskStatus.SUBMITTED
            task.attempts += 1
            task.submitted_at = now
            _rollup(wf, now)
            session.commit()

        # 4. Roll task state up to the workflow.
        _rollup(wf, now)


def _apply_job_status(task: Task, job: JobStatus, now: datetime) -> None:
    task.progress = job.progress
    if job.state == JobState.QUEUED:
        return
    if task.started_at is None:
        task.started_at = now
    if job.state == JobState.RUNNING:
        task.status = TaskStatus.RUNNING
        return
    task.status = _JOB_TO_TASK[job.state]
    task.finished_at = now
    task.error = job.error
    if task.status == TaskStatus.SUCCEEDED:
        task.progress = 100.0


def _rollup(wf: Workflow, now: datetime) -> None:
    statuses = [t.status for t in wf.tasks]
    if wf.status == WorkflowStatus.PENDING and any(s != TaskStatus.PENDING for s in statuses):
        wf.status = WorkflowStatus.RUNNING
        wf.started_at = now
    if all(s in TERMINAL_TASK_STATUSES for s in statuses):
        if all(s == TaskStatus.SUCCEEDED for s in statuses):
            wf.status = WorkflowStatus.SUCCEEDED
        else:
            wf.status = WorkflowStatus.FAILED
        wf.started_at = wf.started_at or now
        wf.finished_at = now
