# MASTER BUILD PLAN — pointer & summary

> **Reconstructed, not original.** The original source document
> (`Ideating.pdf` / "MASTER_BUILD_PLAN v5") is **NOT checked into this repo.**
> This file is a reconstruction assembled from the Stage 01 contract and the
> staged plans in `plans/`. If the original PDF is later located, reconcile
> this summary against it — where they differ, the original + `plans/` win.
>
> **The authoritative, up-to-date breakdown is `plans/`** (files `00-ROADMAP.md`
> through `10-stretch-evaluation.md`). This document is a stable pointer and a
> restatement of the cross-cutting non-negotiables — not the working spec.

---

## What this project is

An AI creative agency platform: a plain-language brief becomes strategy,
concept specs, copy, sketches, and moodboards via a LangGraph-orchestrated
multi-agent pipeline, with two human-in-the-loop gates, an independent critic
pass, image provenance, and an editable-token export handoff.

## Phase-0 contract realized in Stage 01

Stage 01 (Scaffold & Harness) establishes the skeleton every later stage builds
on. Realized here:

- **Directory tree** — `backend/` (installable package `app`, hatchling),
  `frontend/` (Vite + React + TS), root harness files, `plans/` (pre-existing).
- **`.env.example`** — every key OPTIONAL; absence of a key => that provider
  runs in MOCK / DISABLED mode. Committed.
- **`config.py` provider resolution** — one typed settings object that tolerates
  a fully empty environment and never raises on a missing key. Pure string
  logic; no heavy ML imports at module load (MiniLM etc. are lazy-imported in
  later stages).
- **`GET /api/health`** — stable JSON reporting resolved mode of every provider
  (`claude`, `conceptial`, `search`, `embeddings`, `image_gen`, `image_source`,
  `tracing`). Under an empty environment: `status="ok"`, all four providers
  `"mock"`, image lanes disabled, tracing false.
- **Harness** — `Makefile` (`setup`/`dev-*`/`test`/`e2e`/`demo`/`fmt`), a
  backend pytest suite and a frontend vitest suite wired so `make test`
  exercises both and fails if either fails.

## Non-negotiables (cross-cutting, all stages)

**Engineering discipline**
- **TDD** — tests are authored first and define "done" for each stage.
- **Mock-first, zero-keys** — the system boots and `make test` is green on a
  completely empty environment; every provider defaults to mock/disabled.

**Orchestration substrate**
- **LangGraph 1.x** using its real primitives: `interrupt()` for the
  human-in-the-loop gates, `Command` for resumes/routing, `AsyncSqliteSaver`
  for checkpointing, and `Send` for fan-out. Do not replace these with ad-hoc
  substitutes.

**Product invariants that must NEVER be removed**
- The **two human gates** (brief/strategy approval and concept selection).
- **Checkpointing** (durable graph state via the SQLite saver).
- **Divergence** measurement/warning across generated concepts.
- **Critic independence** — the critic uses a model distinct from the generator
  (`CRITIC_MODEL` must differ from `CLAUDE_MODEL` when both resolve real).
- **Image provenance** — every image tracks whether it was generated or sourced
  and from which provider.
- **Editable-token handoff** on export — the export stage emits editable tokens,
  not baked-in final assets.

**Scope guardrails — things this product must NEVER add**
- **No auth** and **no multi-tenancy**.
- **No final brand-asset generation** (it produces directional sketches /
  moodboards / specs, not shippable final brand assets).
- **No trademark screening.**
- **No multi-brief** handling (single brief per run).

## Staged breakdown (authoritative in `plans/`)

| Plan | Focus |
|------|-------|
| `plans/00-ROADMAP.md` | Overall roadmap |
| `plans/01-scaffold.md` | Scaffold & harness (this stage) |
| `plans/02-domain-storage.md` | Domain models + storage |
| `plans/03-graph-spine-gate1.md` | Graph spine + gate 1 |
| `plans/04-fanout-gate2-core.md` | Fan-out + gate 2 core |
| `plans/05-sketches-moodboard-provenance.md` | Sketches, moodboard, provenance |
| `plans/06-export-tokens.md` | Export + editable tokens |
| `plans/07-real-providers.md` | Real provider integrations |
| `plans/08-frontend.md` | Frontend build-out |
| `plans/09-hardening.md` | Hardening |
| `plans/10-stretch-evaluation.md` | Stretch / evaluation |

Refer to `plans/` for the current, authoritative spec of any stage.
