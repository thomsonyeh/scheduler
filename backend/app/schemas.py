from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import dag
from app.models import TaskStatus, WorkflowStatus


class TaskSpec(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    command: str = ""
    depends_on: list[str] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tasks: list[TaskSpec] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _check_dag(self) -> "WorkflowCreate":
        errors = dag.validate([(t.name, t.depends_on) for t in self.tasks])
        if errors:
            raise ValueError("; ".join(errors))
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    command: str
    depends_on: list[str]
    status: TaskStatus
    progress: float
    batch_job_id: str | None
    attempts: int
    error: str | None
    submitted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class WorkflowSummary(BaseModel):
    id: str
    name: str
    status: WorkflowStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    total_tasks: int
    task_counts: dict[TaskStatus, int]
    progress: float = Field(description="Mean task progress, 0-100")


class WorkflowDetail(WorkflowSummary):
    tasks: list[TaskOut]
