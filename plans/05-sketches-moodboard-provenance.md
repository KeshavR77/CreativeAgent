# Sub-plan 05 — Sketches, hybrid moodboard & provenance (Masterplan Phase 3b)

**Goal:** the two visual layers. Every direction gets AI-generated concept sketches and a
hybrid (generated + sourced) moodboard, every image carries complete per-kind provenance, and
the CD can regenerate any single sketch, the whole sketch batch, or any single moodboard slot
(with lane swap). All on mock/placeholder image lanes — real providers land in sub-plan 07.

**Prerequisites:** 04-fanout-gate2-core.

## Scope

### Image lanes (§8.6) — two independent provider interfaces
- `services/imagegen.py` — `ImageGenProvider.generate(prompts) -> list[ImageRef]`. Mock
  implementation writes placeholder bytes to
  `data/generated/{project_id}/{direction_id}/{uuid}.png`, sets `url` to the served path —
  **never base64 into state**. Refs: `kind="generated"`, `provider="generated"`,
  `license="AI-generated"`, `gen_model`, `gen_prompt` (exact prompt → 1:1 regeneration).
  Disabled/no key → raises `ImageGenUnavailable`.
- `services/imagesource.py` — `ImageSourceProvider.search(query, n) -> list[ImageRef]` backed
  by `mock_image_corpus.json`. Refs: `kind="sourced"`, `provider`, `license`, `source_url`,
  `attribution`. Disabled → raises `ImageSourceUnavailable`.
- **Hard provenance rule (all callers):** validate every `ImageRef` before it enters state;
  failing refs are dropped and the slot retried/backfilled. Never surface an image without
  provenance.

### Sketch service (§8.7, §10.7 step 3)
- `SketchService.generate(direction_id, big_idea, territory, n=SKETCH_COUNT)`: n **distinct**
  prompts from big_idea + territory.lens (varying angle/medium — "rough marker sketch,"
  "quick concept thumbnail," …); no brand names, no logos, no legible text-in-image.
  `ImageGenUnavailable` → `kind="placeholder"` refs labeled "sketch generation unavailable";
  the system still runs. Sketches are **always generated, never sourced**.

### Moodboard service (§8.7, §10.7 step 4)
- `MoodboardService.build(direction_id, mood_descriptors, imagery_direction,
  size=MOODBOARD_SIZE, ratio=MOODBOARD_GENERATED_RATIO)` — hybrid by construction:
  1. `n_generated = round(size * ratio)` if gen enabled else 0; `n_sourced = size − n_generated`
     if source enabled else 0; both disabled → `size` placeholders.
  2. One lane down → redirect its share to the enabled lane so the board reaches `size`
     (log which lane absorbed the shortfall).
  3. Generated share: prompts from mood_descriptors + imagery_direction + palette.
  4. Sourced share: 1–3 search queries from the same inputs.
  5. Merge and shuffle (no visual segregation of lanes); each item independently
     provenance-complete.
  6. Total < 4 after provenance filtering → retry shortfall from the available lane, then
     top up with placeholders.

### Graph integration (§9.4, §10.7, §10.9, §12.2)
- Wire steps 3–4 into `explore_territory` (replacing sub-plan 04's stubs) and into the
  post-merge auto sketch pass (merged directions drop parent sketches and get a fresh batch).
- `regenerate_sketch_node`: `mode=="single"` replaces `sketches[index]` (optional prompt
  override); `mode=="batch"` regenerates the full list with fresh prompt variations.
  → straight back to `curation_gate` — **no critique/divergence effect**.
- `regenerate_moodboard_node`: regenerates one slot; `op.kind` optionally forces
  "generated"↔"sourced" for that slot, else keeps the slot's kind. → `curation_gate`.
- Costs: record image-gen calls (`agent="sketches"|"moodboard"`, `model=IMAGE_GEN_MODEL`,
  `output_tokens=image count`) (§8.8).

### API (§12.2, §13)
- `POST /projects/{id}/directions/{did}/regenerate_sketch {index, prompt?}`,
  `.../regenerate_sketches`, `.../regenerate_moodboard_item {index, kind?, prompt?}`
  (prompt ignored for sourced). Same 409/lock discipline as other gate ops.
- Static mount serving `data/generated/`.

## Tests to author first (§16)
- `test_sketches`: `SKETCH_COUNT` refs, all generated, distinct `gen_prompt`s; single regen
  replaces exactly one index (others byte-identical); batch regen replaces the whole list;
  `ImageGenUnavailable` → placeholder fallback with count preserved; neither op touches
  `critique_stale` or divergence.
- `test_moodboard_hybrid`: ratio split within rounding; source-disabled → all-generated full
  board (redirect); gen-disabled → all-sourced; both disabled → all placeholders at `size`;
  kind-swap regen updates lane + provenance fields; provenance-incomplete refs dropped and
  backfilled to keep the board at `size`.
- `test_provenance`: no `ImageRef` failing the per-kind rule ever reaches state, views, or
  export-bound assembly — sketches included.
- Extend `test_fanout` (from 04): each Direction has non-empty `sketches` and a moodboard
  with mixed kinds when both lanes enabled.

## Definition of Done
- All above green with zero keys; full curation flow including sketch/moodboard regeneration
  works end-to-end on placeholders.

## Out of scope
Real fal/Replicate/OpenAI/Pexels/Unsplash calls (07); export rendering (06); UI (08).

## Traps (§19)
- Image bytes/base64 in graph state — persist to `data/generated/`, reference by path.
- Sketch/moodboard regeneration touching divergence or `critique_stale` — it never does.
- Moodboard drifting to generated-only or sourced-only by default — hybrid is the default.
- Sketch generation drifting into final-asset generation — exploratory, always labeled.
