import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.batch import BatchScheduler
from app.batch.mock import MockBatchScheduler
from app.config import Settings
from app.db import make_engine, make_session_factory
from app.models import Base
from app.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _mock_scheduler(settings: Settings) -> MockBatchScheduler:
    return MockBatchScheduler(
        min_duration=settings.mock_min_duration,
        max_duration=settings.mock_max_duration,
        max_queue_delay=settings.mock_max_queue_delay,
        max_concurrent=settings.mock_max_concurrent,
        failure_rate=settings.mock_failure_rate,
    )


def create_app(
    settings: Settings | None = None, scheduler: BatchScheduler | None = None
) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    orchestrator = Orchestrator(session_factory, scheduler or _mock_scheduler(settings))

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        Base.metadata.create_all(engine)
        loop_task = None
        if settings.run_orchestrator:
            loop_task = asyncio.create_task(orchestrator.run_forever(settings.tick_seconds))
        try:
            yield
        finally:
            if loop_task:
                loop_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await loop_task
            engine.dispose()

    app = FastAPI(title="Workflow Scheduler", lifespan=lifespan)
    app.state.session_factory = session_factory
    app.state.orchestrator = orchestrator
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
