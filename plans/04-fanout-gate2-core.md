# Sub-plan 04 — Fan-out, divergence & Gate 2 core (Masterplan Phase 3a)

**Goal:** the backend MVP. K territory-seeded directions explored in parallel via `Send`,
independently critiqued, scored for divergence, and steerable through the curation gate's
text-level ops: promote / kill / annotate / edit / regenerate_field / recritique / fork /
merge / finalize. All on mocks. (Sketch/moodboard steps are stubbed to empty lists here and
land in sub-plan 05.)

**Prerequisites:** 03-graph-spine-gate1.

## Scope

### Fan-out (§9.2, §10.7 steps 1–2 & 5)
- Conditional edge after `seed` returns `[Send("explore_territory", payload) for t in territories]`.
- `explore_territory` branch: **idea** (Conceptial client §8.3 with mock server for tests;
  unset ⇒ `IDEATOR_FALLBACK` = claude_high_temp temp 1.0 or mock) → **spec** (Claude 0.7:
  `ArtDirectionSpec` minus moodboard + `CopyDeck`) → *(sketches/moodboard stubs)* →
  **critic** → returns `{"directions": [d], "costs": [...]}`; failure →
  `{"failed_territories": [label]}` + `agent_failed`. Set `brain` truthfully; emit
  `direction_created{brain}`.
- Inner functions shared/reusable by `ideate_one`, `critique_one`, `regenerate_field_node`.

### Critic (§10.8)
- Fresh context per direction; rubric v1 (distinctiveness, strategic_fit, memorability,
  audience_resonance, feasibility); verdict computed **in code**; `case_against` ≥50 words
  enforced; `critic_model` recorded. Critic scores the strategic/verbal concept only.

### Divergence engine (§11, §8.8)
- `services/embeddings.py`: `EMBEDDINGS_BACKEND=auto` → lazy-import MiniLM, ImportError →
  TF-IDF, `mock` → deterministic hash vectors.
- `services/divergence.py`: pairwise cosine distance over `big_idea + copy.headline +
  art_direction.imagery_direction` of non-killed/non-merged_away directions; `warning` when
  min < `DIVERGENCE_WARN_MIN`; requires ≥2 directions else raises.
- `divergence` node: fan-in target; writes `divergence` + per-direction `divergence_score`;
  emits `divergence_computed`; always routes to `curation_gate`.

### Curation gate & routing nodes (§9.4, §12.2 — text ops only)
- `curation_gate`: `interrupt()` first statement; `match op["op"]` exactly per §9.4:
  - promote/kill/annotate → self-loop re-interrupt.
  - edit → `apply_edit_patch`; divergence-field edits route via `divergence`, others straight
    back; sets `critique_stale=True`.
  - regenerate_field → `regenerate_field_node` (Conceptial for big_idea, else Claude 0.7;
    `critique_stale=True`) → `divergence` → gate.
  - recritique → `critique_one` (clears staleness) → `divergence` → gate.
  - fork → `fork_shell` child (`parent_id`, optional `lens_tweak`) → `ideate_one` →
    `critique_one` → `divergence` → gate.
  - merge → `apply_merge` with `field_choices` (`merged_from`, parents → `merged_away`) →
    `critique_one` → `divergence` → gate.
  - finalize → `refine` if `config.refine_on_finalize` else `package`; requires ≥1 promoted.
- All ops are ordinary graph paths — no bespoke side-job queue.

### refine → package (§10.10)
- `refine` polish pass on promoted directions; `package` builds `ConceptPackage` per promoted
  direction → END.

### API (§12.2, §13 subset)
- `POST /projects/{id}/directions/{did}/promote|kill|annotate|edit|regenerate_field|recritique|fork`,
  `POST /projects/{id}/directions/merge`, `POST /projects/{id}/finalize {refine?}`,
  `GET /projects/{id}/divergence`, `GET /projects/{id}/packages`.
- All 409 outside `awaiting_curation`; all resume under the per-project lock.

## Tests to author first (§16)
- `test_fanout`: K branches all land via the `upsert_directions` reducer; one branch failing
  → `failed_territories` + run continues; each Direction has critique + divergence_score.
  (Extend with sketches/moodboard assertions in sub-plan 05.)
- `test_gates`: curation self-loop re-interrupts; op routing table (which ops hit
  `divergence`, which don't); finalize requires a promotion; 409 discipline.
- `test_edit_ops`: patch application per editable field; divergence-field vs. non-divergence
  routing; `critique_stale` set on edit; merge `field_choices`; fork lineage.
- `test_regenerate_field`: single-field regen validates, marks stale, recomputes divergence
  only for divergence fields.
- `test_divergence`: known-vector fixtures → exact min/mean; warning threshold; killed/
  merged_away excluded; <2 directions raises.

## Definition of Done
- All above green with zero keys; a mock run reaches `awaiting_curation` with K critiqued,
  divergence-scored directions; every §12.2 text op works through the API; finalize produces
  packages (sketch/moodboard fields empty pending sub-plan 05).

## Out of scope
Sketches, moodboards, image provenance enforcement in branches, tokens/export, frontend.

## Traps (§19)
- Missing reducers on Send-written keys (`directions`, `costs`, `failed_territories`).
- Critic sharing model+persona/context with the generator.
- Divergence fed image data — it is text-only by design.
- Presenting `claude_high_temp` output as Conceptial — `brain` must be truthful.
