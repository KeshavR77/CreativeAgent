# Sub-plan 10 — Stretch: evaluation harnesses (Masterplan Phase 7)

**Goal:** measurement tooling that justifies the product's core claims — that Conceptial
ideation diverges more than a plain-Claude baseline, and that the critic's scores are
calibrated. Optional; nothing downstream depends on it.

**Prerequisites:** 09-hardening (needs the stable pipeline + real providers to be meaningful).

## Scope

### A/B divergence harness — `scripts/ab_divergence.py`
- Run the same brief N times per arm: arm A = Conceptial ideator, arm B =
  `claude_high_temp` fallback (and optionally arm C = mock as a floor).
- Reuse `services/divergence.py` verbatim (same embedding backend, same text fields) —
  the harness must measure the production metric, not a variant.
- Report per-arm min/mean pairwise distance distributions + warning rates; machine-readable
  output (JSON) plus a human summary; deterministic seeds where the mock path is involved.

### Critic calibration harness
- Collect rubric scores + verdicts across runs into a dataset (data collection format is
  Keshav's call — leave a TODO marker per §20; do not block).
- Report score distributions per criterion, verdict base rates, and generator-vs-critic
  model pairings, so thresholds (`advance`/`borderline`/`kill`) can be tuned with evidence.

## Tests to author first
- Harness unit tests on fixture run-data: aggregation math, arm labeling, JSON shape.
- Guard: harnesses import the production divergence service (no forked metric logic).

## Definition of Done
- `ab_divergence.py` runs keyless (mock arms) and with keys (real arms), emitting the
  comparison report; calibration harness accumulates and summarizes critique data across
  runs.

## Deferred to Keshav (§20 — leave TODO markers, do not block)
- Real Conceptial deployment URL/auth; API key provisioning.
- Tuning `SKETCH_COUNT`, `MOODBOARD_SIZE`, `MOODBOARD_GENERATED_RATIO`,
  `DIVERGENCE_WARN_MIN`, K default after first real runs.
- Image-gen model/provider choice (cost vs. quality).
- Training-data provenance documentation for Conceptial and the image-gen model.
- Critic calibration data collection design.
