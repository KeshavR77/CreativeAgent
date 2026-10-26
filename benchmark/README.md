# benchmark — agent pipeline vs. one-shot Claude

Compares the staged agent (LangGraph pipeline: research → strategy → gates → K parallel
directions → independent critic → curation → package) against **baseline Claude**: a
single streaming Messages API call asked to produce the target deliverable in one pass.

The target deliverable for both systems is a **research + ideation report** — the
pre-pitch package a brand strategist assembles (competitive audit, category codes,
audience insight, white-space maps, 3–5 positioning territories, a draft messaging
scaffold, creative springboards). Not a finished strategy, not finished creative. The
full spec and scoring rubric live in `baseline_output_spec.md`; the same criteria are
applied to both systems' outputs.

## Input parity

Both systems consume the identical intake object — the agent's `Brief` schema:

| System | How the brief enters |
|---|---|
| Agent | `POST /api/projects` with the Brief JSON, then start + drive gates |
| Baseline | `benchmark/run_baseline.py <brief.json>` — same JSON, one API call |

`briefs/` holds two: `sneaker.json` (the repo's canonical fixture) and `nutrition.json`
(the fictional `sample-rfp.pdf` RFP — brand positioning for a science-founded premium
nutrition brand — distilled into the intake schema; both systems see this distillation,
so neither is advantaged). Note the distillation is a manual, lossy step: if RFP
fidelity matters, re-extract the full PDF text into the `brief` field — the runner
passes it through untruncated.

## The baseline stays a baseline

The lever is the prompt (`baseline_prompt.md`) plus minimal plumbing. Deliberately
absent — these deltas *are* the experiment: live research (the agent has a Tavily
search tool; the baseline must tag unverifiable claims `[verify]` and may not fabricate
sources), image generation, the independent critic, human-in-the-loop steering, and
iteration. No tool loops, sub-agents, or retry/repair passes are added to the baseline.
If a fair comparison requires giving the baseline web search, that is a deliberate
experiment-design change — make it explicitly, don't fold it in.

## Running

Needs `ANTHROPIC_API_KEY` (or an `ant auth login` profile). From the repo root:

```sh
backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/nutrition.json
backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/sneaker.json \
    --model claude-sonnet-4-5 --no-thinking   # match the agent's CLAUDE_MODEL
backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/nutrition.json --dry-run
```

Default model is `claude-opus-4-8` with adaptive thinking and `--max-tokens 32000`
(shared by thinking + report; the run fails loudly if the report is truncated). For a
clean *architecture* comparison (does the pipeline beat one shot, holding the model
fixed?), pass the same `--model` the agent runs with (`CLAUDE_MODEL`, default
`claude-sonnet-4-5`) — models older than the 4.6 family reject adaptive thinking, so
add `--no-thinking`. Running the baseline on a stronger model answers a different
question: can raw capability substitute for structure?

Each run writes `benchmark/runs/<brief>-<model>-<timestamp>/` (gitignored):

```
report.md                   the research + ideation report
conformance_report.json     mechanical checks (structure, [verify] tags, no URLs)
run_meta.json               model, tokens, wall-clock
```

## What gets scored

1. **Rubric score** — `baseline_output_spec.md` applied to `report.md` and to the
   agent's equivalent output, by a human or an LLM judge (keep the judge model
   distinct from both systems' models).
2. **Structural conformance** — the runner's mechanical subset (sections present and
   ordered, 3–5 territories, 2–3 maps, `[verify]` honesty tags, DRAFT marker, brief
   reframe, no fabricated URLs). Passing these is necessary, not sufficient.
3. **Cost & latency** — `run_meta.json` tokens vs. the agent's cost ledger
   (`costs` in graph state), one call vs. many.

## History

An earlier version of this benchmark forced the baseline into the agent's Pydantic
artifact contracts (structured outputs → strategy/verbal-identity/directions JSON) for
field-for-field diffing. That measured a concept-*production* deliverable; the target
deliverable is now the research + ideation report above, scored by rubric instead of
schema. The old runner and prompt are in git history (`git log -- benchmark/`).
