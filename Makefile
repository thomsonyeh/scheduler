.PHONY: install dev backend frontend test lint gen-types build

BACKEND_PORT ?= 8100
export BACKEND_PORT

install:
	cd backend && uv sync
	cd frontend && pnpm install

# Runs backend (:$(BACKEND_PORT)) and frontend (:5173) together; Ctrl-C stops both.
dev:
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) backend & \
	$(MAKE) frontend & \
	wait

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port $(BACKEND_PORT)

frontend:
	cd frontend && pnpm dev

test:
	cd backend && uv run pytest -q
	cd frontend && pnpm exec tsc -b

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint

# Regenerate frontend API types from the FastAPI schema (no running server needed).
# openapi-typescript needs the TS 5 compiler API, so it runs pinned to typescript@5.9.
gen-types:
	cd backend && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > ../frontend/openapi.json
	cd frontend && pnpm dlx --package openapi-typescript@7.13.0 --package typescript@5.9.3 openapi-typescript openapi.json -o src/api/types.ts

build:
	cd frontend && pnpm build
