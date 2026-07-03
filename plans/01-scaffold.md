# Sub-plan 01 — Scaffold & harness (Masterplan Phase 0)

**Goal:** a repo that boots, tests, and reports provider modes with zero API keys — the
foundation every later stage builds on. No product behavior yet.

**Prerequisites:** none.

## Scope

### Repository layout (§4 — create exactly this)
- Root: `README.md`, `MASTER_BUILD_PLAN.md`, `PROGRESS.md`, `.env.example`, `.gitignore`, `Makefile`.
- `backend/` — `pyproject.toml`, `app/` (`main.py`, `config.py`, empty `models/`, `graph/`,
  `services/`, `storage/`, `api/`, `prompts/` packages), `tests/` (with `fixtures/`),
  `scripts/`, `data/` (gitignored, incl. `data/generated/`).
- `frontend/` — Vite + React 18 + TypeScript + Tailwind + zustand + react-router; Vitest + RTL
  configured; `src/` skeleton per §4 (`api/`, `store/`, `views/`, `components/`, `__tests__/`).

### Toolchain & pins (§0.B.9)
- Python 3.12; pin in `pyproject.toml`: `langgraph>=1.0,<2`, `langgraph-checkpoint-sqlite`,
  `langchain-core>=1.0,<2`, `langchain-anthropic` (1.x), FastAPI, SQLAlchemy 2.0, `pytest`,
  `pytest-asyncio`, `httpx`. Record exact pins in `PROGRESS.md`.
- `Makefile` targets: `setup`, `dev-backend`, `dev-frontend`, `test` (pytest + `vitest run`),
  `e2e`, `demo`, `fmt`.

### Configuration (§5)
- `.env.example` verbatim from §5 — every key optional; absence ⇒ mock. Never hard-require a
  secret to boot.
- `config.py`: typed settings; per-provider resolution (real iff its key/URL set); startup
  logs one line per provider.
- `GET /api/health` → `{status, providers:{claude, conceptial, search, embeddings},
  image_gen:{enabled, provider}, image_source:{enabled, provider}, tracing}`.
- Fixtures checked in: `sneaker_brief.json`, `mock_search_corpus.json`, `mock_image_corpus.json`.

### Frontend shell
- App renders with routes stubbed (`ProjectList`, `Studio`, `Cockpit`, `Export`); one trivial
  passing vitest so `make test` exercises both suites.

## Tests to author first
- Backend: health endpoint reports mock modes for all providers when env is empty; config
  resolution flips a provider to "real" when its key is set (use monkeypatched env).
- Frontend: shell smoke test (App renders, router mounts).

## Definition of Done (masterplan Phase 0 DoD)
- `make setup` works from a clean checkout; `make test` runs both suites green.
- `/api/health` shows image_gen/image_source modes; FE shell renders.
- `.env`, `data/` untracked; `git init` done and first commits follow the small-commit rule.

## Out of scope
Any graph node, any Pydantic artifact schema, any real provider call.

## Traps (§19)
- Don't import torch/sentence-transformers at module import time (lazy import comes later,
  but set the pattern now).
- Don't let `config.py` throw on missing keys — missing ⇒ mock, always.
