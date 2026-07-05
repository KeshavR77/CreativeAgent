# AI Creative Agency Platform

A local-first AI creative studio: turn a plain-language brief into strategy,
concept specs, copy, sketches, and moodboards through a LangGraph-orchestrated
multi-agent pipeline — with two human-in-the-loop gates, a critic pass, and
image provenance tracking.

This repository is built in staged sub-plans (see `plans/`). Stage 01 is the
scaffold and harness: directory tree, config/provider resolution, a
`GET /api/health` endpoint, a frontend shell with four placeholder views, and
the test/dev tooling that ties it together.

## Mock-first / zero-keys promise

The invariant that governs everything:

> **With a completely empty environment the system boots, `make test` is
> green, and every provider reports mock / disabled.**

`config.py` never raises on a missing key. Every environment key in
`.env.example` is OPTIONAL — absence of a key means that provider runs in
MOCK / DISABLED mode. You only add keys for the specific providers you want to
activate. `GET /api/health` reports the resolved mode of every provider so you
can see at a glance what is real and what is mocked.

## Quickstart

Prerequisites: Python 3.12 (`python3.12`), `uv` (0.11.x), Node + npm.

```sh
# 1. Create the backend venv (uv), install the backend package + dev extras,
#    and install frontend deps. Idempotent from a clean checkout.
make setup

# 2. Run both test suites (backend pytest + frontend vitest). Green on an
#    empty environment; fails if either suite fails.
make test

# 3. Run the backend (FastAPI + autoreload) at http://127.0.0.1:8000
make dev-backend
#    Health check: curl http://127.0.0.1:8000/api/health

# 4. Run the frontend dev server (Vite)
make dev-frontend
```

No `.env` is required to boot or to pass tests. To activate real providers,
copy `.env.example` to `.env` and fill only the keys you need:

```sh
cp .env.example .env
```

## Other make targets

| Target         | What it does                                              |
|----------------|-----------------------------------------------------------|
| `make setup`   | Backend venv + install (uv), then `npm install`           |
| `make test`    | Backend pytest THEN frontend vitest; fails if either fails |
| `make dev-backend`  | `uvicorn app.main:app --reload`                      |
| `make dev-frontend` | `vite` dev server                                    |
| `make e2e`     | Stub (real e2e lands in sub-plan 06)                      |
| `make demo`    | Stub (demo lands in sub-plan 09)                          |
| `make fmt`     | Best-effort formatters (never fails if one is absent)     |

## Layout

```
backend/    FastAPI app (installable package `app`), pytest suite, fixtures
frontend/   Vite + React + TypeScript shell, Vitest suite
plans/       Authoritative staged build breakdown (00–10)
```

See `MASTER_BUILD_PLAN.md` for the Phase-0 contract and non-negotiables, and
`PROGRESS.md` for what's done / what's next and the resolved dependency pins.
