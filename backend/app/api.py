from collections import Counter
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Task, TaskStatus, Workflow, WorkflowStatus
from app.orchestrator import Orchestrator
from app.schemas import TaskOut, WorkflowCreate, WorkflowDetail, WorkflowSummary

router = APIRouter(prefix="/api")


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator


SessionDep = Annotated[Session, Depends(get_session)]
OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]


def _summary_fields(wf: Workflow) -> dict:
    counts = Counter(t.status for t in wf.tasks)
    total = len(wf.tasks)
    return {
        "id": wf.id,
        "name": wf.name,
        "status": wf.status,
        "created_at": wf.created_at,
        "started_at": wf.started_at,
        "finished_at": wf.finished_at,
        "total_tasks": total,
        "task_counts": {s: counts.get(s, 0) for s in TaskStatus},
        "progress": round(sum(t.progress for t in wf.tasks) / total, 1) if total else 0.0,
    }


def _detail(wf: Workflow) -> WorkflowDetail:
    return WorkflowDetail(
        **_summary_fields(wf), tasks=[TaskOut.model_validate(t) for t in wf.tasks]
    )


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(body: WorkflowCreate, session: SessionDep) -> WorkflowDetail:
    wf = Workflow(
        name=body.name,
        tasks=[
            Task(name=t.name, command=t.command, depends_on=t.depends_on, position=i)
            for i, t in enumerate(body.tasks)
        ],
    )
    session.add(wf)
    session.commit()
    return _detail(wf)


@router.get("/workflows")
def list_workflows(
    session: SessionDep,
    status_filter: Annotated[WorkflowStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[WorkflowSummary]:
    stmt = (
        select(Workflow)
        .options(selectinload(Workflow.tasks))
        .order_by(Workflow.created_at.desc())
        .limit(limit)
    )
    if status_filter is not None:
        stmt = stmt.where(Workflow.status == status_filter)
    return [WorkflowSummary(**_summary_fields(wf)) for wf in session.scalars(stmt)]


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, session: SessionDep) -> WorkflowDetail:
    wf = session.get(Workflow, workflow_id, options=[selectinload(Workflow.tasks)])
    if wf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow not found")
    return _detail(wf)


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, orchestrator: OrchestratorDep) -> WorkflowDetail:
    wf = await orchestrator.cancel(workflow_id)
    if wf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workflow not found")
    return _detail(wf)
