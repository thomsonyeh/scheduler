from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.batch.mock import MockBatchScheduler
from app.db import make_engine, make_session_factory
from app.models import Base, Task, Workflow
from app.orchestrator import Orchestrator


class FakeClock:
    """One clock for both the mock scheduler (monotonic seconds) and the orchestrator (datetime)."""

    def __init__(self) -> None:
        self.t = 0.0
        self._epoch = datetime(2026, 1, 1, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.t

    def now(self) -> datetime:
        return self._epoch + timedelta(seconds=self.t)

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def make_mock(clock: FakeClock, **kwargs) -> MockBatchScheduler:
    """Deterministic mock: every job takes exactly 10s with no queue delay unless overridden."""
    opts = {"min_duration": 10, "max_duration": 10, "max_queue_delay": 0, "max_concurrent": 10}
    opts.update(kwargs)
    return MockBatchScheduler(clock=clock.monotonic, **opts)


@pytest.fixture
def make_orchestrator(session_factory, clock):
    def _make(**mock_kwargs) -> Orchestrator:
        return Orchestrator(session_factory, make_mock(clock, **mock_kwargs), now=clock.now)

    return _make


@pytest.fixture
def create_workflow(session_factory):
    def _create(spec: dict[str, list[str]], commands: dict[str, str] | None = None) -> str:
        commands = commands or {}
        with session_factory() as s:
            wf = Workflow(
                name="test",
                tasks=[
                    Task(name=n, depends_on=deps, command=commands.get(n, f"run {n}"), position=i)
                    for i, (n, deps) in enumerate(spec.items())
                ],
            )
            s.add(wf)
            s.commit()
            return wf.id

    return _create
