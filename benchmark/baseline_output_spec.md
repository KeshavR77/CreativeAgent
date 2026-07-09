# Output spec & scoring rubric — research + ideation report

The target deliverable for **both** systems (one-shot Claude baseline and the agent
pipeline): a strategist's research + ideation package — evidence and structured
*options* a human can lift into a pitch, not a finished strategy and not finished
creative. Apply the same criteria to both outputs for the head-to-head comparison.

**Scoring:** each criterion 0 / 1 / 2 — 0 = absent, 1 = present but partial or generic,
2 = meets the bar. Score sections independently; report the per-deliverable subtotal
and the total. Criteria marked ⚙ are checked mechanically by
`run_baseline.py` (`conformance_report.json`); everything else needs a human or
LLM-judge read (if using an LLM judge, use a model distinct from both systems' models).

## 1. Competitive & category audit

| # | Criterion |
|---|---|
| 1.1 ⚙ | Section present, first in the report |
| 1.2 | Structured profiles of the relevant competitors (RFP-named ones at minimum): positioning, key claims, price architecture, packaging/visual cues, distinctive assets, tone |
| 1.3 | Closes with an explicit "category conventions vs. white space" synthesis |
| 1.4 | Factual claims are grounded (cited with dates if the system has retrieval) or tagged `[verify]` (if it doesn't); no fabricated sources, prices, or stats |

## 2. Category codes (semiotic scan)

| # | Criterion |
|---|---|
| 2.1 ⚙ | Section present |
| 2.2 | Residual / dominant / emergent codes identified, covering both visual and verbal conventions |
| 2.3 | A directional read: where the category is heading, which codes are ripe to break |

## 3. Audience insight brief

| # | Criterion |
|---|---|
| 3.1 ⚙ | Section present |
| 3.2 | Segments + Jobs-to-Be-Done (functional / emotional / social) |
| 3.3 | Lightweight personas with motivations and anxieties; verbatim audience language (real if mined, marked hypothesized otherwise) |
| 3.4 | Ladders to 2–3 candidate human truths with confidence flags — options, not one anointed insight |

## 4. White-space / positioning maps

| # | Criterion |
|---|---|
| 4.1 ⚙ | 2–3 maps present |
| 4.2 | Axes are category-relevant (not generic price/quality by default) and competitors are actually placed |
| 4.3 | Each map explicitly flags an ownable, unoccupied gap and why it's credible for this brand |

## 5. Positioning territories

| # | Criterion |
|---|---|
| 5.1 ⚙ | 3–5 territories |
| 5.2 | Genuinely distinct strategic bets — no two could share a headline |
| 5.3 | Each has: one-line proposition, rationale tied back to the research sections, fitting archetype, conceptual visual/mood direction |
| 5.4 | Each has an honest credibility check ("can the brand deliver this?") and a confidence flag |
| 5.5 | No winner picked — the final bet is explicitly left to the human |

## 6. Messaging framework + brand-architecture scaffold

| # | Criterion |
|---|---|
| 6.1 ⚙ | Section present and marked DRAFT for human refinement |
| 6.2 | Message hierarchy: promise → pillars → proof points, with proof points traceable to the RFP (gaps tagged) |
| 6.3 | Pillar scaffold: purpose / mission / vision / values / personality / promise |
| 6.4 | Territory-dependent choices are flagged rather than silently resolved |

## 7. Creative springboards

| # | Criterion |
|---|---|
| 7.1 ⚙ | Section present, 1–3 springboards |
| 7.2 | Contains at least one "flip" candidate ("it's not X, it's Y") |
| 7.3 ⚙ | Contains at least one explicit reframe of the brief, with what it unlocks |
| 7.4 | Framed as sparks for human creatives, not finished ideas |

## Cross-cutting (score once for the whole report)

| # | Criterion |
|---|---|
| C.1 ⚙ | Modular: all seven sections present in order, deck-ready headers, each liftable on its own |
| C.2 | Two layers everywhere: evidence ("what we found") then synthesis ("so what") — no data without a so-what, no so-what without support |
| C.3 | Options-not-answers throughout, with confidence flags; nothing collapses to a single recommendation |
| C.4 | Sharp and provocative: one-page discipline per section, sound-bite headers; not an exhaustive academic write-up |
| C.5 | Category-calibrated: regulatory / safety / cultural context foregrounded for sensitive categories (health, children's products, finance, …) |
| C.6 | Framework vocabulary used where it fits (positioning statement, archetypes, JTBD, CEPs / mental availability / distinctive assets, semiotics, 4Cs, …) without forcing all of them |
| C.7 | Honesty: no fabricated sources/URLs/stats; uncertainty stated as uncertainty (⚙ partially — the runner checks `[verify]` tags and absence of URLs for the no-retrieval baseline) |
| C.8 | Creatively enabling: a creative could start building from the tensions and options given |

## Known capability asymmetries (note when comparing)

- **Retrieval:** the agent has a search tool; the baseline has none. Grade 1.4 / C.7
  by each system's rule — citations-with-dates where retrieval exists, `[verify]`
  honesty where it doesn't — and expect the baseline's audit and verbatim-language
  depth (1.2, 3.3) to be capped by that gap.
- **Iteration / human steering:** the agent supports human-in-the-loop gates; the
  baseline is one shot. Score first-pass output for both.
