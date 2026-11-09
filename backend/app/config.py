import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(f"SCHEDULER_{name}", default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "sqlite:///./scheduler.db")
    )
    tick_seconds: float = field(default_factory=lambda: float(_env("TICK_SECONDS", "1.0")))
    run_orchestrator: bool = field(
        default_factory=lambda: _env("RUN_ORCHESTRATOR", "true").lower() == "true"
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _env("CORS_ORIGINS", "http://localhost:5173").split(",")
    )

    # Mock batch scheduler knobs
    mock_min_duration: float = field(default_factory=lambda: float(_env("MOCK_MIN_DURATION", "5")))
    mock_max_duration: float = field(default_factory=lambda: float(_env("MOCK_MAX_DURATION", "20")))
    mock_max_queue_delay: float = field(
        default_factory=lambda: float(_env("MOCK_MAX_QUEUE_DELAY", "3"))
    )
    mock_max_concurrent: int = field(default_factory=lambda: int(_env("MOCK_MAX_CONCURRENT", "4")))
    mock_failure_rate: float = field(default_factory=lambda: float(_env("MOCK_FAILURE_RATE", "0")))
