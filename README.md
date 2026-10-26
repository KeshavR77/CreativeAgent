# Creative Agent

An AI creative agency in a box. Drop a client's RFP (PDF) and the platform reads
it, drafts a brief, researches the market, proposes strategy, explores multiple
creative directions — each with its own idea, copy, art direction, sketches, and
moodboard — critiques them with an independent model, and hands off a concept
package.

Two human-in-the-loop gates are always on: strategy approval, and a curation
cockpit where you edit, fork, merge, kill, and promote directions like a creative
director. Two more pause the run when you ask for them — a clarifying-questions
round (`ASK_CLARIFYING_QUESTIONS=true`) and an ideation gate in `manual` mode.

Ideation runs in one of three modes, chosen per project:

| Mode | Behaviour |
|------|-----------|
| `internal` | The reasoning model ideates end-to-end — no pause. |
| `manual`   | Pauses and hands you a packet; brainstorm in any external tool, paste the ideas back, and each is critiqued in-house before you proceed. |
| `auto`     | Brainstorm ⇄ critique rounds run automatically, using the external ideator when one is configured. |

- **Backend** — FastAPI + LangGraph orchestrating the multi-agent pipeline, with
  durable checkpointing (resume mid-run) and a Server-Sent-Events stream.
- **Frontend** — Vite + React + TypeScript; an editorial studio UI (project index,
  live run theater, curation cockpit, export).

## Providers

The reasoning lane is model-agnostic and resolves from whichever key you set:
`ANTHROPIC_API_KEY` selects the Anthropic-compatible lane (Claude, or GLM via
z.ai's Anthropic-compatible endpoint), `MODEL_API_KEY` selects any
OpenAI-compatible endpoint. `MODEL_BASE_URL` defaults to z.ai, so a bare
`MODEL_API_KEY` lands on GLM — but no provider is active until a key is present.
Image generation supports z.ai `glm-image`, fal.ai, Replicate, or OpenAI.

Every provider is optional: with an empty environment the whole pipeline runs on
deterministic mocks, and both suites plus `make e2e` are green with no keys and no
network. `GET /api/health` reports the resolved mode of each provider.

Configure by copying the template and filling only what you need:

```sh
cp .env.example .env
```

## Quickstart

Prerequisites: Python 3.12, [`uv`](https://docs.astral.sh/uv/), Node + npm.

```sh
make setup          # backend venv (uv) + install, then npm install
make test           # backend pytest + frontend vitest (green with no keys)

make dev-backend    # FastAPI at http://127.0.0.1:8080  (run from the repo root so .env loads)
make dev-frontend   # Vite dev server at http://localhost:5173
```

Port 8000 is deliberately left free for a locally-tunneled external ideator
(`IDEATOR_BASE_URL`, see `.env.example`) — the backend runs on 8080 instead.

Then open the frontend, drop a PDF RFP (a fictional sample is at
`sample-rfp.pdf`), and drive the run through the two gates to export.

## Make targets

| Target             | What it does                                              |
|--------------------|----------------------------------------------------------|
| `make setup`       | Backend venv + install (uv), then `npm install`          |
| `make test`        | Backend pytest THEN frontend vitest; fails if either fails |
| `make dev-backend` | `uvicorn app.main:app --reload --port 8080`              |
| `make dev-frontend`| `vite` dev server                                        |
| `make e2e`         | Golden-path end-to-end on mocks (no keys, no network)    |
| `make fmt`         | Best-effort formatters                                   |

## Layout

```
backend/    FastAPI app (installable package `app`) + pytest suite
frontend/   Vite + React + TypeScript app + Vitest suite
```
