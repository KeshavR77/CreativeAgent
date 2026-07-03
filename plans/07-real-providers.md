# Sub-plan 07 — Real providers (Masterplan Phase 4)

**Goal:** flip the system from mock to real, provider by provider, purely via env keys:
Claude for all reasoning roles, Conceptial (or claude_high_temp fallback) for ideation,
Tavily for research, fal/Replicate/OpenAI for image generation, Pexels/Unsplash for image
sourcing, MiniLM/TF-IDF embeddings. Every mock test stays green with no keys.

**Prerequisites:** 06-export-tokens. (Can run in parallel with 08-frontend.)

## Scope

### Chat models (§8.1)
- Real `ChatAnthropic(...)` (streaming) per role; `CLAUDE_MODEL` / `CRITIC_MODEL` resolution;
  **assert `CRITIC_MODEL != CLAUDE_MODEL` when both real** (critic independence).
- Cost tracking from `AIMessage.usage_metadata` → `CostRecord` (§8.8).

### Conceptial client (§8.3)
- `POST {CONCEPTIAL_BASE_URL}/generate` body `{creative_brief, territory:{label,lens},
  n_ideas:1, params:{}}` → `{ideas:[{big_idea, notes}]}`; Bearer auth if key set; 90s
  timeout, 2 retries; unset ⇒ `IDEATOR_FALLBACK` (claude_high_temp | mock). Tiny mock
  Conceptial server for tests. `brain` field always truthful; UI badge distinguishes
  claude_high_temp (frontend wires it in 08).

### Search, embeddings (§5, §8.8)
- Tavily real path behind `TAVILY_API_KEY`; truncate fetched web text before it enters state.
- `EMBEDDINGS_BACKEND=auto`: lazy-import `all-MiniLM-L6-v2` at first use; ImportError →
  scikit-learn TF-IDF.

### Real image lanes (§8.6)
- `ImageGenProvider` real impls per `IMAGE_GEN_PROVIDER` (fal | replicate | openai) +
  `IMAGE_GEN_MODEL` (default `flux/schnell` — fast/cheap suits sketches and refs); persist
  bytes to `data/generated/…`, exact `gen_prompt` recorded for 1:1 regeneration.
- `ImageSourceProvider` real impls per `IMAGE_SOURCE_PROVIDER` (pexels | unsplash) with real
  license names, `source_url`, photographer `attribution`.
- Transient provider failures → node `RetryPolicy`; lane-level unavailability keeps flowing
  through the §8.7 redirect/placeholder fallbacks.

### Observability (§5)
- Optional LangSmith tracing behind `LANGSMITH_TRACING` / `LANGSMITH_API_KEY`; `/health`
  reports `tracing`.

## Tests to author first (§16, Phase 4)
- Extend tests for the real ChatAnthropic code path (constructor/config-level, mocked
  transport — CI has zero keys), Conceptial client against the mock server (auth header,
  timeout, retry, fallback selection), and real provider adapters' **provenance shapes**
  (fal/Pexels response fixtures → correctly populated `ImageRef`s).
- Guard test: entire suite green with an empty environment (mock-first regression).

## Definition of Done (masterplan Phase 4 DoD)
- With `ANTHROPIC_API_KEY` + `FAL_KEY` (+ optionally `PEXELS_API_KEY`): a real run produces
  genuinely varied sketches and a real hybrid moodboard with correct provenance on both
  kinds; costs recorded including image generation; **all mock tests still green with no
  keys**.
- Manual smoke: acceptance-script step 5 (§18) — real run of the sneaker brief, both image
  kinds present and correctly attributed.

## Out of scope
Frontend (08); resume/cancel hardening (09); tuning knobs (deferred to Keshav, §20:
CONCEPTIAL_BASE_URL, key provisioning, SKETCH_COUNT/MOODBOARD_* tuning, image-model choice,
training-data provenance docs).

## Traps (§19)
- Calling providers directly instead of the service interfaces (breaks mock-first + costs).
- Importing torch/sentence-transformers at module import time.
- Secrets in code or state: `grep -r "sk-"` must stay clean; `.env`, `data/` untracked.
- Full fetched web pages or image bytes in graph state.
