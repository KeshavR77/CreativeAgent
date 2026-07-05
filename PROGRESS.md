# PROGRESS

Running log of what's done, what's next, and deviations. The authoritative
staged breakdown lives in `plans/`.

---

## Stage 01 — Scaffold & Harness  ✅ done

Establishes the repo skeleton, provider resolution, health endpoint, frontend
shell, and the test/dev harness. Governing invariant: **empty environment =>
system boots, `make test` is green, every provider reports mock / disabled.**

### What's done

**Root harness (this stage's root-level files):**
- `Makefile` — targets `setup`, `dev-backend`, `dev-frontend`, `test`, `e2e`,
  `demo`, `fmt`. `test` runs backend pytest THEN frontend vitest and fails the
  whole target if either suite fails. `e2e`/`demo` are echo stubs (exit 0).
  `fmt` is best-effort and never fails when a formatter is absent.
- `.env.example` — every key OPTIONAL; absence => mock/disabled. Committed.
- `.gitignore` — extended (existing lines preserved) to also ignore
  `backend/.venv/`, `frontend/node_modules/`, `__pycache__/`, `*.pyc`,
  `.pytest_cache/`, `.ruff_cache/`, `frontend/dist/`, `backend/*.egg-info/`,
  `coverage/`. `.env` and `data/` remain ignored.
- `README.md` — intro, quickstart, mock-first / zero-keys promise.
- `MASTER_BUILD_PLAN.md` — pointer/summary doc (reconstructed; see note below).
- `PROGRESS.md` — this file.

**Backend (owned by the backend agent):**
- Installable package `app` (hatchling), `config.py` provider resolution,
  `app.main:app` with `GET /api/health`, empty package dirs, fixtures, and the
  `test_health.py` / `test_config.py` suites.

**Frontend (owned by the frontend agent):**
- Vite + React + TS shell, four placeholder views (ProjectList / Studio /
  Cockpit / Export), Vitest smoke test.

### What's next — Stage 02 (Domain & Storage)

See `plans/02-domain-storage.md`. Introduces the domain models and storage
layer (SQLAlchemy 2.x, SQLite). Still no real provider calls; still mock-first.
Subsequent stages: 03 graph spine + gate 1, 04 fan-out + gate 2, 05 sketches /
moodboard / provenance, 06 export + editable tokens, 07 real providers, 08
frontend, 09 hardening, 10 stretch / evaluation.

### Resolved dependency pins

Captured from a clean `make setup` (`uv pip freeze --python backend/.venv` /
frontend `package-lock.json`) on macOS (darwin, arm64), 2026-07-03.

**Backend (`backend/.venv`, CPython 3.12.1):**

| Package                       | Declared spec | Resolved version |
|-------------------------------|---------------|------------------|
| langgraph                     | `>=1.0,<2`    | 1.2.7            |
| langgraph-checkpoint-sqlite   | (unpinned)    | 3.1.0            |
| langchain-core                | `>=1.0,<2`    | 1.4.8            |
| langchain-anthropic           | `>=1,<2`      | 1.4.8            |
| fastapi                       | (unpinned)    | 0.139.0          |
| starlette                     | (transitive)  | 1.3.1            |
| uvicorn                       | (unpinned)    | 0.49.0           |
| sqlalchemy                    | `>=2,<3`      | 2.0.51           |
| pydantic-settings             | (unpinned)    | 2.14.2           |
| pydantic                      | (transitive)  | 2.13.4           |
| httpx                         | (unpinned)    | 0.28.1           |
| anyio                         | (transitive)  | 4.14.1           |
| pytest (dev)                  | (unpinned)    | 9.1.1            |
| pytest-asyncio (dev)          | (unpinned)    | 1.4.0            |

**Frontend (`frontend/package-lock.json`, Node 25.2.1 / npm 11.6.2):**

| Package                    | Resolved version |
|----------------------------|------------------|
| react / react-dom          | 18.3.1           |
| react-router-dom           | 6.30.4           |
| zustand                    | 4.5.7            |
| vite                       | 6.4.3            |
| vitest                     | 3.2.6            |
| @vitejs/plugin-react       | 4.7.0            |
| typescript                 | 5.9.3            |
| tailwindcss                | 3.4.19           |
| postcss / autoprefixer     | 8.5.16 / 10.5.2  |
| jsdom                      | 25.0.1           |
| @testing-library/react     | 16.3.2           |
| @testing-library/jest-dom  | 6.9.1            |

**Toolchain:** uv 0.11.6 · python 3.12.1 · node 25.2.1 · npm 11.6.2.

> Deviation vs. the plan's pin list: Vitest was bumped from ~2.x to **3.2.6**
> because Vitest 2.x pins Vite ^5 internally, which clashed with the app's
> Vite 6 (two copies of Vite → a `tsc -b` type error). Vitest 3 declares Vite
> as `^5||^6||^7`, so npm dedupes to a single Vite 6. Behavior-neutral.

### Deviations

- **Test dotenv-hardening (post-build):** the empty-env tests now force
  `APP_DISABLE_DOTENV=1` (autouse fixture in `conftest.py`) and route through
  `get_settings()`, so a local `.env` (which appears from Stage 07 on) can never
  break Stage 01's keyless-first contract. Proven: the backend suite stays green
  with a poison `.env` containing real keys at the repo root.
- Vitest pinned to 3.x (not ~2.x) — see the pins note above.
- `MASTER_BUILD_PLAN.md` is reconstructed; the original `Ideating.pdf` is not in
  the repo (`plans/` + the original are authoritative if the PDF resurfaces).

---

## Stage 02 — Domain Model & Storage  ✅ done

Every data contract (artifacts, graph state, events, views) plus the SQLite
registry/event-log layer, specified by tests first. Still mock-first; zero real
provider calls; zero keys to boot.

### What's done

**Domain models (`backend/app/models/`):**
- `artifacts.py` — the §6.1 schemas: `SourceRef`, `ImageRef` (per-kind
  provenance enforced at the model boundary — a violating ref is
  unconstructible), `Annotation`, `Brief`, `CompetitorNote`, `AudienceNote`,
  `ResearchDossier`, `Strategy`, `VerbalIdentity` (`screened=Literal[False]`),
  `CreativeBrief` (deliberately no visual fields), `Territory`, `PaletteColor`
  (`#RRGGBB`), `TypeChoice`, `ArtDirectionSpec` (moodboard 4–8, empty allowed for
  the sub-plan 04 stub), `CopyDeck`, `CritiqueScore` (rubric v1, `case_against`
  ≥50 words), `Direction` (sketches never sourced), `ConceptPackage`,
  `CostRecord`. Plus the `EDITABLE_FIELDS` / `DIVERGENCE_FIELDS` constants.
- `state.py` — `GraphState(TypedDict, total=False)` with a reducer on every
  parallel-written key: `upsert_directions` (upsert by id) on `directions`,
  `operator.add` on `costs` + `failed_territories`.
- `events.py` — `RunState` enum, `NODE_RUN_STATE` / `GATE_RUN_STATE` maps,
  `NON_RESUMABLE_STATES`, `EventType` + `DirectionChange` constants, documented
  payload TypedDicts.
- `views.py` — `ProjectSummary`, `ProjectView`, `EventOut`.

**Storage (`backend/app/storage/`):**
- `db.py` — SQLAlchemy 2.0 tables `projects` + `events` (unique
  `(project_id, seq)`), engine/session helpers, `data/` auto-created.
- `repo.py` — `RegistryRepo` (CRUD + `list_resumable`), `EventRepo` (atomic
  `append` → per-project seq, `since` backfill, publish-after-commit), `EventBus`
  (in-process pub/sub, scoped per project).

**Tests (authored first):** `test_models.py`, `test_state.py`, `test_storage.py`
— 77 new tests. `make test` → **backend 107 passed, frontend 1 passed**.

### Reconstructed vs. pinned (field-level contract)

The plan pins many fields exactly (ImageRef per-kind provenance, the CritiqueScore
rubric, `screened`, `copy.headline`, `territory.lens`, `direction.brain`, the
event vocabulary, the two storage tables, the `list_resumable` set,
`DIVERGENCE_FIELDS`). Because the §6.1 master schema is not in the repo, the
following were **reconstructed** from downstream usage (plans 03–06) and domain
reasoning — self-consistent and green, but reconcile if the original resurfaces:
the internal fields of `Strategy` / `ResearchDossier` / `CreativeBrief` /
`CopyDeck` / `TypeChoice` / `ConceptPackage` / `CostRecord`;
`CritiqueScore.verdict` values (`ship|revise|kill`) and the 1–5 score scale; the
intermediate `RunState` names (the terminal / `awaiting_*` / `intake` names are
exact); `EDITABLE_FIELDS` membership.

### Deviations / decisions

- **`Direction.sketches` rule is "never sourced", not "all generated".** Plan 02
  §16 lists sketches as all `kind=="generated"`, but plan 05 falls back to
  `kind="placeholder"` when image-gen is unavailable — which is ALWAYS the case
  under zero keys (the test invariant). A strict "all generated" rule would make
  every downstream zero-key DoD impossible, so the enforced model rule is "never
  sourced" (generated + placeholder). Same reconciliation applied to
  `ConceptPackage.sketches`.
- **`copy` field warning silenced** narrowly in pytest config — `copy` is the
  contract field name (divergence reads `copy.headline`; export has a Copy
  section); it shadows pydantic v2's deprecated `BaseModel.copy()` (cosmetic;
  `model_copy()` is the replacement).

### Forward note (constrains Stage 04)

`costs` and `failed_territories` use the `operator.add` reducer (append-only).
Single-direction ops in Stage 04 (edit / recritique / regenerate_field, which
re-route through the `divergence` node) must return **only their own cost
delta**, never the accumulated `costs` list — otherwise the reducer double-counts.
The domain layer is correct; this just records where the reducer choice binds
Stage 04 node returns. (Surfaced by the Stage 02 adversarial review.)

### What's next — Stage 03 (Graph spine & Gate 1)

See `plans/03-graph-spine-gate1.md`: mock model layer (`services/models.py`,
`mock_chat.py`, `search.py`), the spine nodes (interrogate → research →
strategize → **strategy_gate** → verbal → briefwrite → seed), the
`AsyncSqliteSaver` checkpointer, the `RunManager`, SSE, and the Gate-1 endpoints.

---

## Stage 03 — Graph spine & Gate 1  ✅ done

The walking skeleton: a checkpointed LangGraph run goes brief → interrogate →
research → strategize → **strategy_gate (human interrupt)** → verbal → briefwrite
→ seed → END, driven by the RunManager, observable over SSE, entirely on mocks
with zero keys. Built in two TDD slices.

### Slice A — mock model layer + repair loop
- `services/mock_chat.py` — `MockChatModel` (deterministic; seed = project_id +
  role + temperature + schema) + `build_fixture`, a generic validator-respecting
  fixture generator so structured output is valid without hand-writing per node.
- `services/models.py` — `get_chat_model(role)` (mock when keyless; critic role
  resolves `CRITIC_MODEL`; real Claude lazy-imported), `generate_structured`
  (wraps `with_structured_output(..., include_raw=True)`) + the one-shot repair
  loop (`parse_with_repair`: strip ``` fences → retry once → `AgentOutputError`).
- `services/search.py` + `app/resources/mock_search_corpus.json` — deterministic
  corpus-backed Tavily interface (app-owned resource; real Tavily in 07).

### Slice B — graph spine + Gate 1 + RunManager + SSE + API
- `services/prompts.py` + `prompts/*.md` — `{{placeholder}}` templating; the
  briefwrite prompt forbids prescribing visuals (§10.5).
- `graph/nodes.py` — 6 sync spine nodes; each emits agent_started/artifact_written/
  agent_completed via the custom stream and returns ONLY its own new `CostRecord`
  (append-only reducer). `interrogate` interrupts for clarify only when
  `ASK_CLARIFYING_QUESTIONS` is on.
- `graph/gates.py` — `strategy_gate`: `interrupt()` first statement; approve →
  `verbal` (inline edits re-validated), reject → `strategize` with `rejection_notes`.
- `graph/build.py` — `build_graph(checkpointer)`; provider nodes get
  `RetryPolicy(max_attempts=3)` whose `retry_on` excludes `AgentOutputError`.
- `graph/runner.py` — `RunManager`: per-project `asyncio.Task` + `asyncio.Lock`;
  streams `["updates","custom"]`, `durability="sync"`; SOLE durable event writer;
  composes the detail view from registry + checkpoint + interrupt.
- `api/routes_projects.py` + `api/routes_events.py` — Gate-1 REST (create/list/
  detail/start/clarify/gates·strategy, 409 discipline + 422 on invalid edits) and
  hand-rolled SSE (`id:`=seq, `Last-Event-ID` backfill, 15s heartbeat, unsubscribe
  on disconnect). `main.py` lifespan wires storage + `AsyncSqliteSaver` (via
  `AsyncExitStack`) + `RunManager`.

**Tests (authored first):** `test_repair.py`, `test_services.py`,
`test_graph_spine.py`, `test_api.py`. `make test` → **backend 137, frontend 1**.

### Verified
- Independent adversarial review (judging vs. the plan, tracing runtime end-to-end):
  **DoD genuinely met, no blockers.** Checkpointer proof is real (fresh
  `AsyncSqliteSaver` + `build_graph` on the same file DB; a fresh saver on a
  *different* file sees nothing). Keyless import purity confirmed under `env -i`.
  Nodes never write the DB; costs don't double-count; 409/422 discipline holds.
- Post-review fix: inline strategy edits are re-validated (422 at the API boundary,
  `model_validate` in the gate) — closes a validation-at-the-boundary gap; covered
  by two new API tests.

### Known follow-ups (non-blocking; Stage 04+)
- `stream_mode` omits `"messages"`, so `agent_token` isn't emitted yet — re-add
  with batching when token streaming is needed (§9.6 lists it; the spine doesn't
  need it).
- `run_state_changed` fires post-node (LangGraph `updates` semantics), so the
  registry names the just-completed node; terminal states are exact. Cosmetic.
- `clarify` endpoint lacks a 409 guard (behind default-off `ASK_CLARIFYING_QUESTIONS`).
- SSE live-tail (events pushed while connected) verified manually, not yet
  unit-tested; backfill/ordering/`Last-Event-ID` are tested.

### What's next — Stage 04 (Fan-out, divergence & Gate 2 core)
See `plans/04-fanout-gate2-core.md`: `Send` fan-out over territories,
`explore_territory` (idea → spec → critic), the divergence engine, and the
curation gate's text-level ops.

---

## Stage 04 — Fan-out, divergence & Gate 2 core  ✅ done

The backend MVP: K territory-seeded directions explored in parallel via `Send`,
independently critiqued, divergence-scored, and steered through the curation
gate's text ops — all on mocks with zero keys. `make test` → **backend 174,
frontend 1**. Built in two TDD slices (services inline; graph inline).

### Slice A — services (pure Python, ZERO new dependencies)
- `services/embeddings.py` — deterministic mock hash-vectors (keyless default) +
  pure-Python TF-IDF; `auto`/`minilm` lazy-imports sentence-transformers and
  falls back to TF-IDF (absent here). No numpy/sklearn/torch.
- `services/divergence.py` — cosine distance, `compute_divergence` (exact
  min/mean over known vectors), `divergence_report` (excludes killed/merged_away,
  per-direction nearest-neighbour score, warning when min < DIVERGENCE_WARN_MIN,
  <2 raises). Text-only by construction.
- `services/conceptial.py` — Conceptial ideator HTTP client; keyless →
  `ConceptialUnavailable` (the node falls back). Tested via `httpx.MockTransport`.

### Slice B — fan-out + Gate 2 + ops + API
- `services/mock_chat.py` — bespoke-builder registry + `CritiqueScore` (valid
  1–5 scores + ≥50-word case_against) and `PaletteColor` (valid #RRGGBB) builders.
  `get_chat_model` gained `seed_extra` (territory) so branches diverge.
- `graph/exploration.py` — `explore_territory` (idea→spec→critic), reusable
  `ideate_one`/`build_spec`/`critique_one`, `divergence_node` (fan-in), `refine`,
  `package`. Verdict computed in code; `brain` truthful (keyless→"mock"); a
  failed branch → `failed_territories`, run continues.
- `graph/curation.py` — `curation_gate` full op table: promote/kill/annotate
  (self-loop), edit (divergence-field→divergence else gate; critique_stale),
  regenerate_field, recritique (clears staleness→divergence), fork (child
  parent_id/lens_tweak→divergence), merge (merged_from; parents merged_away
  →divergence), finalize (≥1 promoted → refine/package). All ordinary edges.
- `graph/build.py` — `seed` fans out via `Send` per territory → `explore_territory`
  → `divergence` (fan-in) → `curation_gate`; refine→package→END.
- `api/routes_directions.py` — the direction ops + merge + finalize + GET
  divergence/packages; 409 outside awaiting_curation; edit 400 (non-editable) /
  422 (invalid value).

### Confirmed LangGraph fan-out mechanics (empirical probes)
- `Send` fan-out + fan-in: the fan-in node runs ONCE after all branches, seeing
  every direction via the reducer; a failing branch → `failed_territories`, run
  continues.
- **A `Send` branch sees ONLY its payload, not accumulated state** — so
  `explore_territory` receives project_id + territory + context in the payload.

### Tests (§16) — +37
test_embeddings, test_divergence (known-vector exact min/mean), test_conceptial,
test_fanout (K critiqued/scored directions; injected branch failure), test_gates
(op routing + finalize + divergence-event counting), test_edit_ops (patch / fork
lineage / merge), test_regenerate_field, test_directions_api (409 + edit
validation + finalize→packages). The Stage 03 "approve → done" tests were updated
to "approve → awaiting_curation" (the graph now fans out past seed).

### Reconstructed / decisions
- `CritiqueScore.verdict` computed in code: avg of the 5 rubric scores ≥4 → ship,
  ≥2.5 → revise, else kill (reconstructed thresholds).
- per-direction `divergence_score` = nearest-neighbour distance (reconstructed).
- Palette/typography populated via bespoke mock builders; moodboard stays empty
  (sub-plan 05). Mock `seed` emits `settings.K` (default 4) distinct territories.

### Adversarial review (independent, vs. the plan)

DoD genuinely met, no blockers — verified via live probes, not just the author's
tests. All 10 axes pass (reducers on Send-written keys, critic independence,
`brain` truthful, divergence text-only, the op-routing table, RunManager as sole
DB writer, API 409 + edit validation, keyless import purity, no cost
double-counting). Fixes applied post-review:
- **Removed dead duplicate mock builders** in `mock_chat.py` — a second
  `CritiqueScore` + an unused `ArtDirectionSpec` builder that the *stalled* Slice-B
  subagent had appended before it died (my post-failure check only looked for new
  files, missing the in-place edit).
- **K is now honored** — the mock `seed` emits `settings.K` territories (was
  hardcoded to 2); `test_fanout` asserts `len(directions) == K` and that a single
  branch failure leaves K-1 (≥2) still-divergence-scored directions.
- **Added behavioral tests** for `kill` / `annotate` / `recritique` (3 ops that
  had no direct coverage).

### Known follow-ups (non-blocking; Stage 09 hardening)

- A curation op that errors mid-run lands the project in `error` state but the ops
  endpoint still returns 200 (the RunManager swallows node exceptions by design) —
  surface `error` as a non-2xx.
- LangGraph emits msgpack "unregistered type" deprecation warnings for the domain
  models in the checkpoint — register serde types before `LANGGRAPH_STRICT_MSGPACK`
  becomes an error.
- fork/merge/regenerate/recritique invoke models but record no `CostRecord`
  (under-counting) — add when the cost ledger matters.

### What's next — Stage 05 (Sketches, hybrid moodboard & provenance)
See `plans/05-sketches-moodboard-provenance.md`: the two image lanes
(`imagegen`/`imagesource`), the sketch + hybrid moodboard services, hard
per-kind provenance at every caller, and the regenerate-sketch/moodboard ops.

---

## Stage 05 — Sketches, hybrid moodboard & provenance  ✅ done

Two visual layers on mock/placeholder image lanes: every direction gets AI
sketches + a hybrid (generated + sourced) moodboard, every image carries complete
per-kind provenance, and the CD can regenerate any sketch / the whole batch / any
moodboard slot (with lane swap). `make test` → **backend 198, frontend 1**. ZERO
new dependencies (no Pillow / numpy).

### Slice A — image lanes + services
- `services/imagegen.py` — the mock writes a real 1×1 PNG (base64 byte constant —
  no Pillow) to `data/generated/{pid}/{did}/{uuid}.png`; `url` = served path
  (never base64). `kind=generated` + full provenance. Disabled → `ImageGenUnavailable`.
- `services/imagesource.py` — corpus-backed sourced refs (provider/license/
  source_url/attribution); provenance-incomplete entries dropped. Disabled →
  `ImageSourceUnavailable`.
- `services/sketches.py` — `SKETCH_COUNT` distinct prompts (varying medium; no
  logos/text); `ImageGenUnavailable` → placeholder fallback (count preserved).
  Never sourced. Single/batch regen.
- `services/moodboard.py` — hybrid: `round(size*ratio)` generated + rest sourced;
  a downed lane redirects its share to the live lane; both down → placeholders;
  shortfall backfilled to `size`; deterministic shuffle (no lane segregation);
  kind-swap slot regen.
- `app/resources/mock_image_corpus.json` — 12 enriched entries.

### Slice B — graph + API
- `exploration.attach_visuals` wires sketches + moodboard into `explore_territory`
  (+ image `CostRecord`s); fork/merge also attach *fresh* visuals (merged drops the
  parents' sketches, §10.9).
- `curation.py` — `regenerate_sketch` / `regenerate_sketches` /
  `regenerate_moodboard_item` ops route straight back to the gate (NO
  `critique_stale`, NO divergence — unlike the text ops).
- `api/routes_directions.py` — the 3 regenerate endpoints; `main.py` static-mounts
  `/generated`.

### Model reconciliation (surfaced by Stage 05)
- **`ArtDirectionSpec.moodboard` relaxed from "4–8" to "empty or ≥4".**
  `MOODBOARD_SIZE` defaults to 9, which the old ≤8 cap (a Stage-02 reconstruction)
  rejected. The floor of 4 is the model invariant (plan 05 step 6); the exact size
  is service-enforced. Updated the Stage-02 moodboard tests accordingly.

### Tests (§16) — +21
test_sketches, test_moodboard_hybrid, test_provenance, test_regenerate_visuals,
extended test_fanout (non-empty visuals + hybrid moodboard when lanes enabled),
test_directions_api (regenerate endpoints).

### What's next — Stage 06 (Export, tokens & packaging)
See `plans/06-export-tokens.md`: deterministic (no-LLM) token + markdown export
renderers with full per-image provenance, and `make e2e` on mocks.

---

## Stage 06 — Export, tokens & packaging  ✅ done (closes Masterplan Phase 3)

The tool-native editable handoff — the product's actual deliverable. Deterministic,
LLM-free renderers + the golden-path e2e. `make test` → **backend 207, frontend 1**;
`make e2e` → **exit 0**.

### What's built
- `services/tokens.py` — W3C `tokens.json` (`$value`/`$type`) + `tokens.css`
  custom properties from a package's palette/typography. Deterministic, no model
  calls.
- `api/routes_export.py` — the deterministic markdown renderer
  (`render_export_markdown`, pure/unit-tested) + endpoints `GET
  /projects/{id}/export.md`, `/tokens.json`, `/tokens.css` (all accept
  `?direction_id=`). Order: H1 (first 8 words of brief) → per-package H2
  (territory) → Strategy → Big idea → Sketches (provenance-labeled) → Art direction
  (palette/type/imagery + moodboard per-tile provenance, BOTH kinds) → Copy → Why
  it works → Assets & licensing → AI-disclosure footer (generated/sourced counts;
  names badged "unscreened").
- `main.py` includes the export router.
- `scripts/e2e_golden.py` + `make e2e` — golden path with image lanes ON: create →
  start → Gate 1 → fan-out → Gate 2 → regenerate sketch/sketches/moodboard → edit →
  kill → merge → fork → recritique → promote → finalize(refine) → assert a complete
  package (provenance-complete sketches, mixed-provenance moodboard, valid tokens,
  export.md sections). Exits 0/1.

### Deviation
- `make e2e` drives the app **in-process via TestClient** rather than a live
  uvicorn server (reliable & deterministic; the full app/graph/service logic is
  exercised — only the network/uvicorn process is out of scope).

### Tests (§16) — +9
test_tokens (W3C shape, parseable CSS, determinism), test_export (all sections,
both provenance kinds, disclosure counts, unscreened badge, determinism),
test_directions_api (export/token endpoints + 404-before-finalize).

### Phase 3 complete
Stages 04 (fan-out + Gate 2) + 05 (visuals) + 06 (export) — the full backend MVP
runs brief → editable handoff end-to-end on mocks with zero keys.

### What's next — the 07 ∥ 08 parallel window
Per the roadmap, `plans/07-real-providers.md` (real Claude / Conceptial / Tavily /
fal / Pexels behind the same interfaces) and `plans/08-frontend.md` (the React UI)
can proceed **in parallel** after 06; they rejoin at 09 (hardening).

---

## Stage 07 — Real providers  ✅ done (Phase 4) · 08 built concurrently

Real provider paths behind env keys, **guarded so keyless stays 100% green**.
Backend `pytest` → **229 passed** (incl. the follow-ups). No real keys/network in tests (mocked
transports/fixtures); `grep -r "sk-"` clean; the Anthropic SDK stays lazy-imported.

### Done + tested
- **Chat (§8.1):** real `ChatAnthropic(model, streaming, max_retries=2)` per role;
  `resolve_model_name` enforces **critic independence** (CRITIC_MODEL must differ
  from CLAUDE_MODEL when real — raises otherwise); `usage_to_cost` maps
  `AIMessage.usage_metadata` → CostRecord. (test_providers_chat)
- **Conceptial (§8.3):** real `POST /generate` {creative_brief, territory:{label,lens},
  n_ideas, params} → [{big_idea, notes}]; Bearer auth when keyed; 90s timeout, 2
  transport retries; keyless/error → `ConceptialUnavailable` (node falls back; brain
  truthful). (test_conceptial via MockTransport)
- **Image gen (§8.6):** real **fal** adapter (POST → image URL → download + persist
  bytes; exact gen_prompt for 1:1 regen); key-guarded dispatch. (test_providers_image)
- **Image source (§8.6):** real **pexels** + **unsplash** adapters (pure
  response→ImageRef provenance mapping + thin HTTP wrappers; incomplete photos
  dropped); key-guarded. (test_providers_image)
- **Key-guard reconciliation:** a provider name activates its real adapter ONLY when
  its key is present — so Stage 05/06 tests (which set `IMAGE_GEN_PROVIDER=mock` /
  `IMAGE_SOURCE_PROVIDER=pexels` WITHOUT keys) still hit the mock. Mock-first preserved.
- **Embeddings (§8.8):** already `auto → MiniLM (lazy) → TF-IDF` from Stage 04.

### Follow-ups — now DONE (backend 229)
- **Tavily real search** ✅ — `tavily_to_sources` (pure) + `_real_search` (behind
  `TAVILY_API_KEY`); fetched web text truncated to 500 chars before entering state
  (§19). (test_providers_image)
- **Replicate + OpenAI** gen adapters ✅ — key-guarded, same pattern as fal
  (openai b64 → decode+persist; replicate output URL → download+persist). (tested)
- **Cost-wiring** ✅ — `generate_structured` captures `usage_metadata` into a
  per-context (per fan-out branch) contextvar; the spine nodes' `_cost` reads it so
  real runs record real chat-token counts (0 for the mock — keyless unchanged). (tested)
- **LangSmith** ✅ — env-driven; langchain 1.x reads `LANGSMITH_TRACING` /
  `LANGSMITH_API_KEY` natively and `/health` reports `tracing` (no code needed).

Minor refinements left for later: per-call cost granularity inside the fan-out
branch (explore records one branch-level CostRecord); a live real-key smoke run.

### DoD status
The primary real path (ANTHROPIC + FAL + PEXELS) is implemented and unit-tested at
the adapter/config level; all mock tests stay green with zero keys. A live real-key
smoke run (§18 step 5) is the manual acceptance step (operator's keyed environment).

---

## Independent review of 07 + 08 (+ fixes applied)  ·  `make test` → backend 231, frontend 56

Two adversarial reviews (backend providers; frontend UI). **07: DoD met, no blockers**
(critic independence unbypassable, key-guard preserves mock-first, provenance shapes,
no bytes/pages in state, cost contextvar per-branch-safe [stress-tested], no secrets,
lazy imports, green under `env -i`). Fixes applied:
- **07-F1** — the fan-out now records real chat costs: `generate_structured` accumulates
  `usage_metadata` into a per-branch contextvar and `explore_territory` reads it (was a
  flat `output_tokens=1`).
- **07-F2** — deleted dead `usage_to_cost`; **07-F3** — added the conceptial→claude_high_temp
  fallback test. **07-F4** (Tavily retry hardening) → folded into Stage 09.

**08: three real frontend↔backend contract bugs, all fixed + tested:**
- single-field regenerate had a dead prop and NO reachable control → added a per-field
  ⟳ button in `DirectionCard` (§19 coarse-control violation) + test;
- `MergeModal` sent dotted `field_choices` (`copy.headline`, …) that backend `_merge`
  ignored (only `big_idea` took effect) → `_merge` now applies each editable field
  granularly from the chosen parent + test;
- SSE resume sent `?lastEventId=` but the backend read only the `Last-Event-ID` header →
  every reconnect replayed from seq 0 → the endpoint now honors the query param
  (resume from seq) + test.
`npm run build` compiles clean; types.ts verified field-for-field faithful to the backend.

---

## Stage 09 — Hardening ✅ (`make test` → backend 239, frontend 56; e2e + demo exit 0)

Restart-resilience, cancel/retry, gate purity, and the demo seed — the mechanic
(an **errored** graph resumes from its last checkpoint via `astream(None, cfg)`;
only the pending node/branch re-runs) was probed empirically before building.

- **Boot recovery (§9.5):** `RunManager.resume_all()` re-drives every `list_resumable()`
  row from its checkpoint; called in the lifespan after `app.state` is wired (no-op on
  a clean boot). Gated/terminal runs are excluded (they wait on a human / are done).
- **`POST /projects/{id}/cancel`** → `RunManager.cancel()`: cancels the in-flight task
  (releasing its lock), marks `cancelled` (terminal, non-resumable), emits `run_cancelled`.
  Idempotent; `CancelledError` is not swallowed by the error handler.
- **`POST /projects/{id}/retry`** → `RunManager.retry()`: error-state only (else 409),
  resumes from the checkpoint with `None` input — the failed node re-runs, completed
  nodes/branches do NOT (**Send-branch idempotency = checkpoint discipline, not flags**).
- **Gate purity:** a resume through the gate re-runs the gate node from its `interrupt()`
  but re-runs NO pre-gate node — verified by counting `research` completions across the
  approve (stays 1).
- **Tavily hardening (07-F4):** bounded timeout + transport retries, and a failing/slow/
  malformed Tavily now **degrades to the mock corpus** (warns) instead of failing the run.
- **`scripts/dev_seed.py` / `make demo`:** seeds one project paused at Gate 2 into `data/`
  on mocks (no keys), so `make dev-backend`+`make dev-frontend` open a populated Cockpit.

New tests (`test_resume.py` +5, `test_api.py` +2, `test_providers_image.py` +1): kill-at-Gate-2
→ restart (fresh RunManager, same DBs) → state intact + curation ops/finalize still work (the
**§18 headline**); errored-run retry re-runs research and reaches Gate 1; retry-when-not-errored
rejected; cancel → cancelled + event + not-resumable; gate re-entry purity; `/cancel` 200+idempotent,
`/retry` 409; Tavily→mock degradation. Still zero-keys, `grep sk-` clean, `data/`+`.env` untracked.

---

## Stage 10 — Stretch: evaluation harnesses ✅ (`make test` → backend 249, frontend 56)

Measurement tooling for the product's core claims. Built as an importable package
`app/evaluation/` (unit-testable) with thin CLIs in `scripts/`; nothing in the
product runtime imports it.

- **A/B divergence** (`app/evaluation/divergence_ab.py` + `scripts/ab_divergence.py`):
  runs a brief N times per arm — `conceptial` / `claude_high_temp` / `mock` — and
  reports per-arm mean/min pairwise distance, worst-case min, warn-rate, and brain
  counts, with a treatment-vs-baseline verdict. **Reuses the production metric
  verbatim** (`from app.services.divergence import divergence_report`; a guard test
  asserts `divergence_ab.divergence_report is divergence_report` — no forked math).
  Keyless it runs the mock arm only; real keys in the env add the arms they cover.
- **Critic calibration** (`app/evaluation/calibration.py` + `scripts/critic_calibration.py`):
  collects rubric scores + verdicts across runs into an accumulating JSONL dataset,
  reports score distribution per criterion, verdict base rates, and generator→critic
  model pairings. Data-collection FORMAT left as a `TODO(§20 — Keshav)`.

Tests (`test_eval_divergence.py` +6, `test_eval_calibration.py` +4): aggregation math,
arm labeling, JSON-serializable shape, the production-metric guard, JSONL
accumulate-across-runs, and one integration run of the mock arm through the real
graph. Both CLIs smoke-run keyless (`env -i`): the A/B report emits `mock runs=2
mean=0.505 …`, the calibration report emits verdict base rates + per-criterion
histograms. **DoD met** — harnesses run keyless (mock arms) and, with keys, the real arms.

### LangGraph msgpack forward-compat warning — RESOLVED
LangGraph used to log `Deserializing unregistered type app.models.artifacts.* … blocked
in a future version` on every checkpoint read (`aget_state`/resume). Fixed in
`app/storage/checkpoint.py`: `open_checkpointer()` sets the saver's serde to a
`JsonPlusSerializer(allowed_msgpack_modules=…)` whose allowlist is **introspected** from
`app.models.artifacts` (every `BaseModel`/`Enum`, so a new artifact can't be forgotten).
The allowlist is complete because those artifact models are the only non-LangGraph-safe
types the graph checkpoints — which is exactly why they were the only types that warned.
All checkpointer sites (lifespan + both eval scripts + the test fixtures) go through the
one helper. Note: a specific allowlist makes any *missed* type silently deserialize to a
raw dict (not an error), so `test_checkpoint_serde.py` round-trips a fully-nested Direction
and asserts every nested value comes back as its model type; the whole graph/restart suite
runs through the serde too. A keyless `ab_divergence` run now emits 0 msgpack warnings.

---

## Build status: all 10 stages complete
Stages 01–10 are built on `main`. `make test` → backend 254 + frontend 58;
`make e2e` + `make demo` exit 0; zero-keys-to-boot holds; `grep sk-` clean;
`data/` + `.env` untracked.

---

## Full vulnerability + bug review (+ fixes)

Two adversarial security passes (server-side + client/config) found **no exploitable
vulnerabilities** — parameterized ORM, server-generated UUID/hash IDs as the only
values reaching the filesystem, hardcoded outbound hosts, boundary re-validation of
edits, no dangerous deserialization/shell, no CORS/XSS sinks. One defense-in-depth
note (no `javascript:` guard on `ImageRef.url`, not client-settable).

A high-effort bug pass fixed five real correctness bugs (each with a regression test);
two candidates were refuted (SSE reconnect double-count — `sse.ts` keeps a high-water
mark across reconnects; `direction_updated` no-op — the op-response `setView` + refetch
apply it):
- **`EditableField` stale display** — `display` was seeded once and never re-synced, so
  single-field regenerate (and any external update) showed the old value until remount;
  added a `useEffect` re-sync (skips in-progress/pending edits).
- **Mode banner stuck on "MOCKED"** — the store checked provider `!== 'live'` but the
  backend reports `"real"/"mock"`, so a fully-keyed run stayed labelled mocked; fixed to
  `!== 'real'` and corrected the `'live'` test fixture that masked it.
- **Eval A/B harness crash** — `run_arm` called `divergence_report` (raises on <2 active
  directions); now skips degenerate runs.
- **Event double-count backstop** — `applyEvent` tracked `lastSeq` but didn't gate on it;
  added `seq <= lastSeq` drop so any replay can't double-count costs/tokens.
- **Regenerated `big_idea` kept stale `brain`** — now updates `brain` to the ideator that
  produced the new idea.

Deferred (lowest severity, needs a UI/product call): the store reducer drops
`agent_failed`/`agent_completed` (run-level failures still surface via
`run_state_changed(error)`; only a single failed *territory* is currently invisible).
