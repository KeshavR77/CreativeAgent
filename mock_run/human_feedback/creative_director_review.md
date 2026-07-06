# Creative Director review — mock run `f4b7c21e` (sneaker brief)

**Reviewer:** Keshav (mock persona)
**Brief:** *"Launch a sustainable sneaker brand for runners who are sick of greenwashing."*
**Scope:** narrative record of every human-in-the-loop decision in this mock run. The
machine-readable payloads that the graph actually consumes live beside this file
(`01_clarify_answers.json` … `04_curation_session_ops.json`).

---

## Clarify (optional interrogate gate)

Asked what success looks like and who the audience is. Two answers set the guardrails the
whole run leans on: **zero retracted claims beats maximum sales**, and the buyer is a
**data-literate runner whose default is distrust**. Everything downstream gets judged
against those two sentences.

## Gate 1, round 1 — strategy REJECTED

The first strategy came back as *"the eco-friendly performance shoe… Run green. No
compromise."* That is the exact artifact the brief exists to attack: four unverifiable
adjective claims and a dateless carbon-neutral pledge. If our own strategy can't survive
our audience's sniff test, nothing downstream will. Sent back with notes: **the enemy is
not carbon, it's unsubstantiated claims — position us as the brand that shows its work.**

## Gate 1, round 2 — strategy APPROVED, with one inline edit

Round two ("publishes the complete, audited footprint of every shoe — proof before
promises") is the right strategy. One edit at the gate: the key message *"Proof, not
promises."* is category-generic — a bank could run it. Replaced with
**"Don't take our word for it. Read the receipt."** — the receipt is ours, and the line
tells the reader to do the thing the brand is built on. (This lands in state as
`edited_by_human = true`.)

## Gate 2 — curation session (17 ops)

Three directions came out of fan-out: **The Receipt** (ship, 4.2), **Built To Rebuild**
(revise, 3.8), **Anti-Hype** (revise, 3.0). Divergence healthy (min 0.44, no warning).
The session, in order:

| # | Op | Target | Reasoning |
|---|----|--------|-----------|
| 1 | annotate | The Receipt | Strongest opener; log the legal caveat on publishing audited numbers before anything else. |
| 2 | regenerate_sketch (slot 3, prompt override) | The Receipt | Sketch drew the whole shoe — too literal. Want the receipt-tongue macro. Visual op only: critique and divergence untouched. |
| 3 | regenerate_moodboard_item (slot 5, kind → generated) | The Receipt | Caliper stock photo was off-mood; generate on-palette instead. |
| 4 | edit `copy.headline` | Built To Rebuild | "Your next shoe is the one you already own." is polite to a fault. The confrontation is the concept: **"Stop buying new shoes."** Divergence field → recompute + stale critique. |
| 5 | recritique | Built To Rebuild | Fresh verdict on the sharper card: 3.8 revise → **4.0 ship** (memorability up, and the new case_against correctly flags retailer channel conflict). |
| 6 | regenerate_field `copy.headline` | Anti-Hype | One salvage attempt before the axe. |
| 7 | annotate | Anti-Hype | The words were never the problem — it's a media strategy wearing a brand strategy's clothes. The honesty beat survives inside The Receipt's "publish the misses" pillar. |
| 8 | kill | Anti-Hype | Per the annotation. (Critique left stale on the corpse — faithful to the op routing.) |
| 9 | fork (lens tweak: "the shoebox is the receipt") | The Receipt | Cheap experiment: does the receipt stretch into unboxing? |
| 10–11 | annotate + kill | The Receipt Box (fork) | Critic agreed (3.6 revise): packaging execution, not a platform. Keep the mail-back-lid beat for later. |
| 12 | merge | Receipt + Rebuild | The real move: Receipt has the brand ritual, Rebuild has the product truth. Base = Receipt; pull Rebuild's edited headline via `field_choices`. Parents → `merged_away`; sketches and moodboard regenerate fresh on the child. |
| 13 | edit `big_idea` | The Living Receipt (merged) | Merge copies fields verbatim, so the child still carried Receipt's big idea unchanged. Wove the mile-500 rebuild in: the receipt gets a second page. |
| 14 | recritique | The Living Receipt | Fused concept scores **4.2 ship**; case_against correctly warns the two promises now share one credibility budget. |
| 15 | annotate | The Living Receipt | "Proof at purchase, proof at mile 500." |
| 16 | promote | The Living Receipt | The one. |
| 17 | finalize (refine: true) | — | One promoted direction → refine → package. |

## Closing assessment

The pipeline earned its keep twice: Gate 1 caught the strategy drifting into the exact
failure mode the brief bans, and Gate 2's critic independently produced the
retailer-conflict and shared-credibility-budget objections that shaped the final concept.
Deliverable: one concept package, **The Living Receipt**, with candidate names still
unscreened (flagged), every image provenance-tagged, and the AI disclosure in the export.
