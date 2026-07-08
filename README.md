# Creative Agent

An AI creative agency in a box. Drop a client's RFP (PDF) and the platform reads
it, drafts a brief, researches the market, proposes strategy, explores multiple
creative directions — each with its own idea, copy, art direction, sketches, and
moodboard — critiques them with an independent model, and hands off a concept
package. Two human-in-the-loop gates keep a person in control: strategy approval,
and a curation cockpit where you edit, fork, merge, kill, and promote directions
like a creative director.

- **Backend** — FastAPI + LangGraph orchestrating the multi-agent pipeline, with
  durable checkpointing (resume mid-run) and a Server-Sent-Events stream.
- **Frontend** — Vite + React + TypeScript; an editorial studio UI (project index,
  live run theater, curation cockpit, export).

## Providers

The reasoning lane is model-agnostic. It runs on **GLM (z.ai)** via the
Anthropic-compatible endpoint by default, and also supports Anthropic (Claude) or
any OpenAI-compatible endpoint. Image generation supports z.ai `glm-image`,
fal.ai, Replicate, or OpenAI. Every provider is optional: with an empty
environment the whole pipeline runs on deterministic mocks (and `make test` is
green with no keys). `GET /api/health` reports the resolved mode of each provider.

Configure by copying the template and filling only what you need:

```sh
cp .env.example .env
```

## Quickstart

Prerequisites: Python 3.12, [`uv`](https://docs.astral.sh/uv/), Node + npm.

```sh
make setup          # backend venv (uv) + install, then npm install
make test           # backend pytest + frontend vitest (green with no keys)

make dev-backend    # FastAPI at http://127.0.0.1:8000  (run from the repo root so .env loads)
make dev-frontend   # Vite dev server at http://localhost:5173
```

Then open the frontend, drop a PDF RFP (a sample is at
`cerebelly-sample-rfp.pdf`), and drive the run through the two gates to export.

## Make targets

| Target             | What it does                                              |
|--------------------|----------------------------------------------------------|
| `make setup`       | Backend venv + install (uv), then `npm install`          |
| `make test`        | Backend pytest THEN frontend vitest; fails if either fails |
| `make dev-backend` | `uvicorn app.main:app --reload`                          |
| `make dev-frontend`| `vite` dev server                                        |
| `make e2e`         | Golden-path end-to-end on mocks (no keys, no network)    |
| `make fmt`         | Best-effort formatters                                   |

## Layout

```
backend/    FastAPI app (installable package `app`) + pytest suite
frontend/   Vite + React + TypeScript app + Vitest suite
```
