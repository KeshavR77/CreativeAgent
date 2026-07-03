# Sub-plan 02 — Domain model & storage (Masterplan Phase 1)

**Goal:** every data contract in the system (artifacts, graph state, events) plus the SQLite
registry/event-log layer, fully specified by tests before any graph code exists.

**Prerequisites:** 01-scaffold.

## Scope

### Artifact schemas — `models/artifacts.py` (§6.1, field names are contract)
- `SourceRef`, `ImageRef` (provenance-mandatory: `kind` literal generated/sourced/placeholder,
  per-kind required fields), `Annotation`, `Brief`, `CompetitorNote`, `AudienceNote`,
  `ResearchDossier`, `Strategy`, `VerbalIdentity` (`screened: Literal[False]`),
  `CreativeBrief`, `Territory`, `PaletteColor` (hex validated `#RRGGBB`), `TypeChoice`,
  `ArtDirectionSpec` (moodboard 4–8 `ImageRef`), `CopyDeck`, `CritiqueScore`
  (`case_against` ≥50 words, verdict literal), `Direction` (sketches all
  `kind=="generated"`, `critique_stale`, `status`, `brain`), `ConceptPackage`, `CostRecord`.
- Encode the **editable-fields** and **divergence-fields** lists (§6.1 end) as constants here —
  later stages import them rather than restating.

### Graph state — `models/state.py` (§6.2)
- `GraphState(TypedDict, total=False)` exactly per §6.2.
- Reducers: `upsert_directions` (upsert by id — parallel Send branches append safely),
  `operator.add` on `failed_territories` and `costs`. Every key written by parallel branches
  has a reducer.

### Events & run state — `models/events.py`, `models/views.py` (§6.3)
- `RunState` enum (intake … done/cancelled/error) + node→RunState map.
- Event type constants with payload shapes (`run_created` … `run_cancelled`, incl.
  `direction_updated.change` values: edit, regenerate_field, regenerate_sketch,
  regenerate_sketches, regenerate_moodboard_item, recritique).

### Storage — `storage/db.py`, `storage/repo.py` (§7)
- SQLAlchemy 2.0 + SQLite; `data/` auto-created and gitignored.
- Tables: `projects(id PK, state, brief_excerpt, error, created_at, updated_at)`;
  `events(id PK AUTOINC, project_id, seq, type, payload JSON, at)` with unique
  `(project_id, seq)`.
- `RegistryRepo`: create/get/list/update_state, `list_resumable()` = states not in
  {awaiting_strategy_approval, awaiting_curation, done, cancelled, intake}.
- `EventRepo`: atomic `append(project_id, type, payload) -> seq`; `since(project_id, seq)`;
  publishes to in-process pub/sub (SSE consumes it in sub-plan 03).
- Keep repos narrow so Postgres (+ `PostgresSaver`) can swap in later.

## Tests to author first (§16)
- `test_models`: schema happy/sad paths; hex validation; `case_against` length; **ImageRef
  per-kind provenance** (generated needs `gen_model`+`gen_prompt`; sourced needs
  `source_url`+`attribution`; all need `provider`+`license`); `Direction.sketches` all
  `kind=="generated"`.
- `test_storage`: registry CRUD + `list_resumable` filtering; event append atomicity, seq
  uniqueness per project, `since()` ordering; pub/sub delivery.
- Reducer unit tests: `upsert_directions` on insert vs. replace-by-id, concurrent-append shape.

## Definition of Done (masterplan Phase 1 DoD)
- `test_models` + `test_storage` green with zero keys, including `Direction.sketches` and
  per-kind `ImageRef` rules.

## Out of scope
Graph nodes, checkpointer, API routes, SSE wiring (pub/sub interface only).

## Traps (§19)
- Provenance is validated at the model boundary — an `ImageRef` failing its per-kind rule
  must be unconstructible, not merely flagged.
- State stays lean by design: `ImageRef.url` is a path/URL, never base64.
