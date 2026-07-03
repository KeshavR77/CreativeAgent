# Sub-plan 06 — Export, tokens & packaging (Masterplan Phase 3c)

**Goal:** the tool-native editable handoff — the product's actual deliverable. Deterministic
(no-LLM) renderers for design tokens, the markdown concept package with full per-image
provenance, and the AI-assist disclosure. Closes masterplan Phase 3: `make e2e` passes on
mocks with zero keys.

**Prerequisites:** 05-sketches-moodboard-provenance.

## Scope

### Token service — `services/tokens.py` (§15)
- `tokens.json` (W3C-style design tokens) and `tokens.css` (custom properties) from a
  package's palette/typography. Machine-readable design output stays tokens/vector, never
  raster.

### Export renderer — `api/routes_export.py` (§15)
One deterministic markdown doc:
- H1 = first 8 words of brief; per package H2 = territory label.
- Order: Strategy → Big idea → **Sketches** (thumbnails, each labeled `AI-generated via
  <gen_model>, prompt: "<gen_prompt>"`) → Art direction (palette, typography, imagery/layout
  prose, moodboard with per-tile provenance line — generated: `AI-generated via <gen_model> —
  prompt: "<gen_prompt>"`; sourced: `<provider>, <license>, © <attribution> (<source_url>)`)
  → Copy → Why it works.
- "Assets & licensing" section itemizing every sketch and moodboard image by kind.
- Footer AI disclosure naming sketch and moodboard generation explicitly, itemizing generated
  vs. sourced counts separately (§2). Candidate names badged "unscreened."

### API (§13)
- `GET /projects/{id}/export.md` (text/markdown), `GET /projects/{id}/tokens.json`,
  `GET /projects/{id}/tokens.css` — all accepting `?direction_id=`.
- `ConceptPackage` assembly confirmed complete: strategy, big_idea, sketches (copied per
  §10.10), art_direction, copy, rationale.

### E2E golden path — `scripts/e2e_golden.py`, `make e2e` (§16)
Against a live dev backend, all mocks: create sneaker project → start → Gate 1 approve →
Gate 2 → regenerate one sketch; regenerate the full sketch batch on another direction;
regenerate one moodboard item and swap its kind; edit a headline; kill the weakest; merge
two; fork one; recritique; promote the merged → finalize(refine=true) → assert package
completeness incl. non-empty provenance-complete sketches, mixed-provenance moodboard, valid
tokens, and export.md containing Sketches section + Assets & licensing + AI disclosure.
Exit 0/1.

## Tests to author first (§16)
- `test_tokens`: valid W3C-shaped JSON and parseable CSS custom properties from a fixture
  package; `?direction_id=` filtering.
- `test_export`: markdown contains a Sketches section, per-tile provenance lines of **both**
  kinds, Assets & licensing itemization, and an AI disclosure naming sketch and moodboard
  counts; deterministic (same input → identical output); unscreened badge present.
- `test_api` completion: full route surface incl. export/token endpoints, error envelope
  `{error:{code,message}}`.

## Definition of Done (closes masterplan Phase 3)
- All Phase-3 tests (04+05+06) green; full curation incl. sketch/moodboard regeneration;
  **`make e2e` passes on mocks**.

## Out of scope
Real providers (07), frontend Export view (08).

## Traps (§19)
- Export must never contain a provenance-incomplete image — reuse the §8.6 validator, don't
  re-implement it.
- Renderers are deterministic and LLM-free; no model calls anywhere in this sub-plan.
