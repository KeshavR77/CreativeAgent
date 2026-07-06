# mock_run — a complete simulated run with human-in-the-loop feedback

A hand-authored but **schema-exact** walkthrough of one full pipeline run on the
canonical fixture brief (*"Launch a sustainable sneaker brand for runners who are sick of
greenwashing."*, K=3). Every agent-output document validates against the live Pydantic
contracts in `backend/app/models/artifacts.py`, and every human-feedback document uses the
exact resume-payload shape the gates consume (`graph/gates.py`, `graph/curation.py`).

Purpose: reviewable examples of what the agents produce at each node, paired with mock
human feedback that exercises both blocking gates — usable as documentation, demo
material, and fixtures for gate/curation tests.

**Verify:** `backend/.venv/bin/python mock_run/validate.py`

## The run, in order

```
brief ──▶ clarify? ──▶ research ──▶ strategize ──▶ [GATE 1] ──▶ verbal ──▶ briefwrite ──▶ seed
                                        ▲   reject │ approve(+edits)
                                        └──────────┘
seed ──▶ explore ×3 (idea→spec→sketches→moodboard→critic) ──▶ divergence ──▶ [GATE 2]
[GATE 2] ops: annotate, visual regens, edit, recritique, regenerate_field, kill,
              fork, kill, merge, edit, recritique, annotate, promote, finalize
──▶ refine ──▶ package ──▶ export
```

| Stage (node) | Agent output | Human feedback |
|---|---|---|
| intake | `00_input_brief.json` | — |
| interrogate (clarify gate, opt-in) | questions are fixed in the node | `human_feedback/01_clarify_answers.json` |
| research | `agent_outputs/01_research_dossier.json` | — |
| strategize, round 1 | `agent_outputs/02_strategy_v1.json` | **Gate 1 reject** `human_feedback/02_…reject.json` |
| strategize, round 2 | `agent_outputs/03_strategy_v2.json` | **Gate 1 approve + inline edit** `human_feedback/03_…approve.json` → `edited_by_human=true` |
| verbal | `agent_outputs/04_verbal_identity.json` (names unscreened by design) | — |
| briefwrite | `agent_outputs/05_creative_brief.json` (no visual prescriptions, §10.5) | — |
| seed | `agent_outputs/06_territories.json` | — |
| explore ×3 | `agent_outputs/07a…07c_direction_*.json` | — |
| divergence (fan-in) | `agent_outputs/08_divergence_initial.json` | — |
| **curation gate** | | **17 ops** `human_feedback/04_curation_session_ops.json` + narrative `creative_director_review.md` |
| ↳ visual regens + annotate on The Receipt | `agent_outputs/09_direction_the_receipt_v2.json` | ops 1–3 |
| ↳ fork of The Receipt | `agent_outputs/10_direction_fork_receipt_box.json` | ops 9–11 |
| ↳ merge Receipt+Rebuild → edit → recritique → promote | `agent_outputs/11_direction_merged_living_receipt.json` | ops 12–16 |
| ↳ divergence after merge (<2 active → nulls) | `agent_outputs/12_divergence_final.json` | — |
| ↳ gate view at finalize | `agent_outputs/13_curation_summary_final.json` | op 17 (finalize, refine=true) |
| package | `agent_outputs/14_concept_package.json` | — |
| (cost tracking throughout) | `agent_outputs/15_cost_ledger.json` | — |
| export (deterministic, LLM-free) | `deliverables/export.md`, `tokens.json`, `tokens.css` | — |

## Fidelity notes — deliberate, faithful-to-code details

- **Verdicts are code-computed** (`exploration.compute_verdict`): every critique's scores
  average to its verdict (≥4.0 ship / ≥2.5 revise / else kill); `case_against` ≥50 words.
- **Provenance is complete per kind** on all 51 images: generated refs carry
  `gen_model` + exact `gen_prompt` (1:1 regeneration contract); sourced refs carry
  `source_url` + `attribution`. Sketches are never sourced.
- **Prompt formats** match the services byte-for-byte: sketch prompts follow
  `services/sketches.py::_prompts` (rotating mediums, "no brand names, no logos, no
  legible text in the image"); moodboard prompts follow `services/moodboard.py::_gen_prompts`.
- **Moodboards are hybrid by construction**: 9 tiles = 3 generated + 6 sourced
  (`MOODBOARD_SIZE=9`, ratio 0.34), lanes interleaved.
- **Op routing side-effects are honored**: visual regens (ops 2–3) touch neither critique
  nor divergence; divergence-field edits mark critiques stale; Anti-Hype dies with
  `critique_stale=true` because it was never recritiqued after its headline regen.
- **Merged direction quirks**: sketches were generated *at merge time*, so their
  `gen_prompt`s reference the pre-edit big idea; `divergence_score` is `null` because only
  one direction remained active (`12_divergence_final.json` shows the <2-directions nulls);
  `rationale` in the package is code-assembled (`big_idea — key_message`).
- **Brains are truthful**: two directions record `conceptial`, one records
  `claude_high_temp` (simulating a Conceptial timeout falling back per `IDEATOR_FALLBACK`).
- **Export invariants**: unscreened-names badge, per-tile provenance lines for both kinds,
  Assets & licensing itemization, AI disclosure with separate generated/sourced counts.

## What is fictional

Everything. The run simulates a fully keyed environment (`claude-sonnet-4-5`,
critic `claude-opus-4-1`, Conceptial, fal `flux/schnell`, Pexels) but no providers were
called: research sources, statistics, photo URLs (`example.com`) and photographer names
are invented; image URLs point at files that don't exist. Model/cost figures are
illustrative. Do not treat the dossier's numbers as real research.
