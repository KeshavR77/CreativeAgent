# Roadmap — AI Creative Agency Platform

Derived from `MASTER_BUILD_PLAN v5` (Ideating.pdf). The masterplan remains the single source
of truth; each sub-plan slices it into an independently executable, test-first stage. Where a
sub-plan is silent, defer to the masterplan section it cites.

## Staging: MVP → Production

| # | Sub-plan | Masterplan phase | Milestone it unlocks |
|---|----------|------------------|----------------------|
| 01 | [Scaffold & harness](01-scaffold.md) | Phase 0 | Repo boots, `make test` runs, mock-first config in place |
| 02 | [Domain model & storage](02-domain-storage.md) | Phase 1 | All Pydantic contracts + SQLite registry/event log green |
| 03 | [Graph spine & Gate 1](03-graph-spine-gate1.md) | Phase 2 | **Walking skeleton**: brief → strategy → human approval, checkpointed, streamed over SSE |
| 04 | [Fan-out, divergence & Gate 2 core](04-fanout-gate2-core.md) | Phase 3a | **Backend MVP**: K parallel directions, critic, curation ops (edit/regen-field/fork/merge/finalize) on mocks |
| 05 | [Sketches, hybrid moodboard & provenance](05-sketches-moodboard-provenance.md) | Phase 3b | Visual layers with hard provenance guarantees (mock/placeholder lanes) |
| 06 | [Export, tokens & packaging](06-export-tokens.md) | Phase 3c | **Full mock product**: `make e2e` green end-to-end with zero API keys |
| 07 | [Real providers](07-real-providers.md) | Phase 4 | Claude, Conceptial, Tavily, image gen/source live behind env keys; mocks still green keyless |
| 08 | [Frontend](08-frontend.md) | Phase 5 | **Usable product**: full flow drivable from the UI in <5 min on mocks |
| 09 | [Hardening](09-hardening.md) | Phase 6 | **Production-ready (local)**: resume-anywhere, cancel, gate purity, `make demo` |
| 10 | [Stretch: evaluation](10-stretch-evaluation.md) | Phase 7 | A/B divergence harness, critic calibration |

Phase 3 of the masterplan is deliberately split into 04/05/06 — it is the largest phase and
these three slices have clean seams (graph ops vs. image services vs. renderers).

## Dependency graph

```
01 → 02 → 03 → 04 → 05 → 06 → 07 → 09 → 10
                         └───→ 08 ──┘
```

- 04–06 are strictly ordered (06's export needs 05's provenance; 05 hangs off 04's directions).
- 08 (frontend) can start against 06's mock backend and proceed in parallel with 07.
- 09 requires both 07 and 08 (its acceptance script exercises real keys + UI refresh recovery).

## Non-negotiables carried through every sub-plan

1. **TDD** (§0.A): each sub-plan starts by authoring that stage's tests as failing tests; its
   DoD is literally "those tests pass." Never commit red. `make test` before every commit.
2. **LangGraph 1.x** (§ preamble): `interrupt()`/`Command(resume=…)` for gates,
   `AsyncSqliteSaver` checkpointing, `Send` fan-out, `astream` multi-mode. No hand-rolled
   state machine, never compile without the checkpointer.
3. **Mock-first** (§0.B): the whole system builds, runs, and passes tests with **zero API
   keys**. Providers activate individually by env-key presence.
4. **Never remove** (§0.B.8): the two blocking human gates, checkpointed resumability, the
   divergence metric, critic independence, image provenance, the editable/token handoff.
5. **Never add** (§0.B.7): auth, multi-tenancy, final-brand-asset generation, trademark
   screening, more than one brief per run.
6. Keep `PROGRESS.md` current — done / next / deviations and why.

## Canonical fixture

Everywhere: *"Launch a sustainable sneaker brand for runners who are sick of greenwashing."*
