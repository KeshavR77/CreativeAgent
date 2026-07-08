# benchmark — agent pipeline vs. one-shot Claude

Compares the staged agent (LangGraph pipeline: research → strategy → gates → K parallel
directions → independent critic → curation → package) against **baseline Claude**: a
single Messages API call asked to produce the same deliverable in one pass.

The trick that makes outputs comparable: the baseline call uses **structured outputs
composed from the repo's real Pydantic contracts** (`app/models/artifacts.py`). Baseline
Claude is forced into the exact same `Strategy`, `VerbalIdentity`, `CreativeBrief`,
`Territory`, `CopyDeck`, `PaletteColor`, `TypeChoice` shapes the agent emits, so every
artifact can be diffed field for field.

## Input parity

Both systems consume the identical intake object — the agent's `Brief` schema:

| System | How the brief enters |
|---|---|
| Agent | `POST /api/projects` with the Brief JSON, then start + drive gates |
| Baseline | `benchmark/run_baseline.py <brief.json>` — same JSON, one API call |

`briefs/` holds two: `sneaker.json` (the repo's canonical fixture) and `cerebelly.json`
(the `MockBrief.pdf` RFP — brand positioning for a science-founded baby-food brand —
distilled into the intake schema; both systems see this distillation, so neither is
advantaged).

## Output format mapping

| Agent artifact | Baseline field | Notes |
|---|---|---|
| `Strategy` | `strategy` | identical schema |
| `VerbalIdentity` | `verbal_identity` | identical; `screened: false` enforced |
| `CreativeBrief` | `creative_brief` | identical; no-visuals rule prompted |
| `territories` (seed node) | `directions[].territory` | identical schema |
| `Direction.big_idea` | `directions[].big_idea` | |
| `Direction.art_direction` | `directions[].art_direction` | minus `moodboard` — no images in a text call |
| `Direction.copy` | `directions[].copy` | identical schema |
| `Direction.sketches[].gen_prompt` | `directions[].sketch_prompts` | prompts are the comparable text artifact |
| `Direction.critique` | `directions[].critique` + code | rubric + case_against from the model; **verdict computed in code with the agent's exact rule** (`exploration.compute_verdict`) |
| curation → promote | `recommended_territory_label` + rationale | baseline self-selects; agent gets a human |
| `ConceptPackage` / `export.md` | `artifacts/concept_package.json` / `baseline_export.md` | assembled + rendered by the repo's own package/export code |

**Deliberately absent from the baseline** — these deltas *are* the experiment:
live research (agent has a search tool), actual image generation, the independent
critic (baseline self-critiques with the same model and context; the agent's critic is a
different model with a fresh context), human-in-the-loop steering, and iteration
(reject/edit/regenerate/fork/merge). `brain` on lifted directions is recorded as
`claude_high_temp` — the closest truthful label the contract offers for a plain
Claude call.

## Running

Needs `ANTHROPIC_API_KEY` (or an `ant auth login` profile). From the repo root:

```sh
backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/cerebelly.json
backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/sneaker.json \
    --model claude-sonnet-4-5 --k 3          # match the agent's CLAUDE_MODEL
backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/cerebelly.json --dry-run
```

Default model is `claude-opus-4-8`. For a clean *architecture* comparison (does the
pipeline beat one shot, holding the model fixed?), pass the same `--model` the agent
runs with (`CLAUDE_MODEL`, default `claude-sonnet-4-5`). Running the baseline on a
stronger model answers a different question: can raw capability substitute for
structure?

Each run writes `benchmark/runs/<brief>-<model>-<timestamp>/` (gitignored):

```
baseline_output.json        raw parsed model output
artifacts/                  agent-schema artifacts (strategy, verbal identity, creative
                            brief, territories, direction_NN.json, concept_package.json)
baseline_export.md          rendered by the repo's own export renderer
compliance_report.json      contract checks + divergence report
run_meta.json               model, tokens, wall-clock
```

## What gets scored

1. **Contract compliance** — the agent satisfies these by construction; the baseline is
   graded on them: exactly K directions, unique territories, valid recommendation,
   unscreened names, ≥50-word `case_against`, 3 distinct sketch prompts, no brand names
   leaked into sketch prompts, palette/typography validity (enforced at parse time).
2. **Divergence** — the production `services/divergence.py` scores the baseline's K
   directions on the same three text fields the agent is scored on. Note the embeddings
   backend: keyless it's `mock` (hash vectors — not meaningful); install/enable MiniLM or
   TF-IDF (`EMBEDDINGS_BACKEND`) for numbers comparable to a real agent run.
3. **Cost & latency** — `run_meta.json` tokens vs. the agent's cost ledger
   (`costs` in state; see `mock_run/agent_outputs/15_cost_ledger.json` for the shape),
   one call vs. many.
4. **Quality** — side-by-side human read of `baseline_export.md` vs. the agent's
   `export.md` for the same brief (or an LLM-judge pass — a natural next step; keep the
   judge model distinct from both systems' models).

## Fairness notes

- The baseline prompt (`baseline_prompt.md`) collapses the agent's staged prompts into
  one instruction set and states the same semantic contracts the agent's validators
  enforce, including the explicit warning that divergence is measured. Prompting the
  baseline *toward* the agent's standards is intentional — the benchmark asks what the
  architecture adds beyond good instructions.
- The verdict rule (ship ≥ 4.0 / revise ≥ 2.5 / kill) runs in harness code for both
  systems; neither model is trusted to grade its own verdict.
- One call, one repair-free shot: the runner does not retry validation failures — the
  agent gets a repair loop, the baseline's schema is enforced server-side by structured
  outputs, which roughly cancels out.
