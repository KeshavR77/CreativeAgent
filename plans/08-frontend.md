# Sub-plan 08 — Frontend (Masterplan Phase 5)

**Goal:** the three surfaces — Studio (live theater), Cockpit (steering), Export (handoff) —
making the full flow drivable from the UI on mocks in under 5 minutes, including sketch and
moodboard regeneration, with hard-refresh recovery mid-run.

**Prerequisites:** 06-export-tokens (mock backend feature-complete). Runs in parallel with 07.

## Scope

### Foundations (§4, §14)
- `api/types.ts` mirrors §6 field names exactly — **same-commit rule** with any backend model
  change. `api/client.ts` typed REST client; `api/sse.ts` EventSource wrapper with backoff +
  `Last-Event-ID` resume. `store/useProjectStore.ts` (zustand): project view + event-reducer
  applying SSE events; mode banner state from `/health`.

### ProjectList & Studio (§14.1)
- ProjectList: create (brief + K), list with RunState chips.
- Studio: `PipelineSpine` (node progress), `AgentStream` (batched tokens), `LaneGrid`
  skeleton cards with sketch-thumbnail placeholders filling in as `direction_created`
  arrives; `CostFooter`; mode banner when anything is mocked + distinct badge when the
  ideator ran on `claude_high_temp`.

### Cockpit (§14.2) — the steering surface
- `StrategyGatePanel` (Gate 1): approve with inline edits / reject with notes.
- `DirectionCard`: territory chip; `EditableField` for every text/color/type field
  (§6.1 editable list); `DivergenceBadge`; `CritiquePanel` + `StaleCritiqueBadge`
  (sketch/moodboard regen never triggers staleness); status/actions promote/kill/fork/
  merge-select; `MergeModal` (field_choices; moodboard as whole-board A/B choice; sketches
  excluded — auto-regenerated post-merge); `UnscreenedBadge` on candidate names.
- `SketchGrid`: 3–6 `ImageTile`s, each with `ProvenanceTag` ("AI-generated · <model>",
  prompt on hover) and per-tile ⟳ → `/regenerate_sketch`; "Regenerate all sketches" →
  `/regenerate_sketches`.
- `MoodboardGrid`: 4–8 tiles tagged by kind (generated: "AI-generated · <model>"; sourced:
  "<provider> · <license> · © attribution" linking `source_url`); per-tile ⟳ →
  `/regenerate_moodboard_item`; `SourceToggle` (generated ⇄ sourced) passing `kind`.
- Buttons disabled mid-flight (per-project lock; 409 handling).

### Export (§14.3)
- `PackageDoc` with Sketches section (thumbnails + "AI-generated" note) and mixed-provenance
  moodboard tags; `TokenExport` (tokens.json/tokens.css download); `AssetLicensePanel`
  listing every image with provenance; `AiDisclosureNote` itemizing generated vs. sourced
  counts.

## Tests to author first (§16, vitest + RTL)
- `store.test.ts`: event reducer per event type; RunState-driven view routing.
- `sseReducer.test.ts`: ordering, backfill after simulated disconnect.
- `editableField.test.tsx`: inline edit → PATCH payload shape; optimistic vs. confirmed.
- `directionCard.test.tsx`: field rendering, stale badge on edit, action wiring.
- `mergeModal.test.tsx`: field_choices incl. whole-board moodboard pick; sketches absent.
- `sketchGrid.test.tsx` (new): N tiles with provenance; per-tile ⟳ calls
  `/regenerate_sketch`; "Regenerate all" calls `/regenerate_sketches`.
- `moodboardGrid.test.tsx` (new): correct provenance per kind; `SourceToggle` passes `kind`
  to `/regenerate_moodboard_item`.

## Definition of Done (masterplan Phase 5 DoD)
- All frontend tests green; full flow drivable from the UI on mocks in <5 min including
  sketch/moodboard regeneration; **hard refresh mid-run recovers** (SSE resume + project
  view rehydration).

## Out of scope
Restart-resilience beyond refresh (09); real-provider visual QA (after 07 lands).

## Traps (§19)
- `types.ts` drifting from backend models — same-commit rule.
- Frontend must never talk to model/image/search providers directly (§2).
- Never surface an image tile without its provenance tag.
- Coarse control only is a product violation — inline edit, single-field regen,
  single-sketch regen, batch regen, single-tile regen with kind swap are all required.
