"""Baseline benchmark: one Claude API call standing in for the whole agent pipeline.

Feeds the same intake `Brief` JSON the agent receives to a single
`messages.parse()` call whose output schema is composed from the repo's REAL
Pydantic contracts (app/models/artifacts.py) — so the baseline's output is
directly comparable, field for field, with the agent's artifacts. Post-
processing mirrors the agent's own rules: the critique verdict is computed in
code (never trusted from the model), divergence is scored by the production
divergence service, and the deliverable is rendered by the repo's own
deterministic export renderer.

Usage (from the repo root; needs ANTHROPIC_API_KEY or an `ant auth login`
profile):

    backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/cerebelly.json
    backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/sneaker.json \
        --model claude-sonnet-4-5 --k 3
    backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/cerebelly.json --dry-run

Pass `--model` matching the agent's CLAUDE_MODEL to isolate architecture
(pipeline + gates + independent critic) from model capability.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from pydantic import BaseModel, Field  # noqa: E402

from app.api.routes_export import render_export_markdown  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.graph.exploration import compute_verdict, direction_id  # noqa: E402
from app.models.artifacts import (  # noqa: E402
    ArtDirectionSpec,
    Brief,
    ConceptPackage,
    CopyDeck,
    CreativeBrief,
    CritiqueScore,
    Direction,
    PaletteColor,
    Strategy,
    Territory,
    TypeChoice,
    VerbalIdentity,
)
from app.services.divergence import divergence_report  # noqa: E402


# --------------------------------------------------------------------------- #
# baseline output schema — composed from the agent's real contracts.           #
# Deviations are deliberate and documented:                                    #
#   * art direction omits `moodboard` (a single text call cannot make images); #
#   * sketches become `sketch_prompts` (comparable to the agent's gen_prompts);#
#   * critique omits `verdict`/`critic_model` — the verdict is computed in     #
#     code with the agent's exact rule, mirroring exploration.critique_one.    #
# --------------------------------------------------------------------------- #
class BaselineArtDirection(BaseModel):
    imagery_direction: str
    mood_descriptors: list[str] = Field(default_factory=list)
    layout_notes: str = ""
    palette: list[PaletteColor] = Field(default_factory=list)
    typography: list[TypeChoice] = Field(default_factory=list)


class BaselineCritique(BaseModel):
    distinctiveness: int
    strategic_fit: int
    memorability: int
    audience_resonance: int
    feasibility: int
    case_against: str


class BaselineDirection(BaseModel):
    territory: Territory
    big_idea: str
    art_direction: BaselineArtDirection
    copy: CopyDeck
    sketch_prompts: list[str] = Field(default_factory=list)
    critique: BaselineCritique


class BaselineOutput(BaseModel):
    strategy: Strategy
    verbal_identity: VerbalIdentity
    creative_brief: CreativeBrief
    directions: list[BaselineDirection]
    recommended_territory_label: str
    recommendation_rationale: str


# --------------------------------------------------------------------------- #
# prompt rendering (same {{placeholder}} convention as app/services/prompts)   #
# --------------------------------------------------------------------------- #
def render_prompts(brief: Brief, k: int) -> tuple[str, str]:
    template = (REPO / "benchmark" / "baseline_prompt.md").read_text(encoding="utf-8")
    # anchor on the headings at line start (the intro prose mentions them inline)
    _, system_and_user = template.split("\n## System\n", 1)
    system, user = system_and_user.split("\n## User\n", 1)
    values = {
        "k": str(k),
        "brief": brief.brief,
        "brand_name": brief.brand_name or "(unnamed — naming is part of the job)",
        "audience": brief.audience or "(not specified)",
        "constraints": "\n".join(f"- {c}" for c in brief.constraints) or "- (none)",
    }
    for key, value in values.items():
        system = system.replace(f"{{{{{key}}}}}", value)
        user = user.replace(f"{{{{{key}}}}}", value)
    return system.strip(), user.strip()


# --------------------------------------------------------------------------- #
# post-processing: lift baseline output into the agent's artifact contracts    #
# --------------------------------------------------------------------------- #
def to_agent_direction(run_id: str, d: BaselineDirection, model_id: str) -> tuple[Direction, list[str]]:
    """Build an agent-schema Direction from a baseline direction.

    Returns the Direction plus any contract violations hit on the way (a
    violation downgrades the field rather than failing the run — contract
    compliance is one of the things being benchmarked).
    """
    violations: list[str] = []
    critique = None
    try:
        critique = CritiqueScore(
            **d.critique.model_dump(),
            # verdict is computed in code, exactly as the agent does (§10.8)
            verdict=compute_verdict(d.critique),
            critic_model=model_id,  # self-critique: same model, same context
        )
    except Exception as exc:  # noqa: BLE001 - record, don't crash the benchmark
        violations.append(f"critique for '{d.territory.label}' violates the contract: {exc}")
    direction = Direction(
        id=direction_id(run_id, d.territory.label),
        territory=d.territory,
        big_idea=d.big_idea,
        # `brain` has no "baseline" value; claude_high_temp is the closest
        # truthful label for a plain Claude call (see benchmark/README.md).
        brain="claude_high_temp",
        art_direction=ArtDirectionSpec(**d.art_direction.model_dump(), moodboard=[]),
        copy=d.copy,
        sketches=[],
    )
    return direction.model_copy(update={"critique": critique}), violations


def compliance_checks(out: BaselineOutput, k: int) -> list[dict]:
    """The agent enforces these by construction; the baseline is graded on them."""
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    labels = [d.territory.label for d in out.directions]
    check("produced exactly K directions", len(out.directions) == k, f"{len(out.directions)}/{k}")
    check("territory labels are unique", len(set(labels)) == len(labels), ", ".join(labels))
    check(
        "recommendation points at a real territory",
        out.recommended_territory_label in labels,
        out.recommended_territory_label,
    )
    check("names are marked unscreened", out.verbal_identity.screened is False)
    for d in out.directions:
        prefix = f"[{d.territory.label}]"
        words = len(d.critique.case_against.split())
        check(f"{prefix} case_against >= 50 words", words >= 50, f"{words} words")
        check(
            f"{prefix} exactly 3 distinct sketch prompts",
            len(d.sketch_prompts) == 3 and len(set(d.sketch_prompts)) == 3,
            f"{len(d.sketch_prompts)} prompts",
        )
        leaked = [
            n
            for n in out.verbal_identity.names
            if any(n.lower() in p.lower() for p in d.sketch_prompts)
        ]
        check(f"{prefix} no brand names in sketch prompts", not leaked, ", ".join(leaked))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", help="path to a Brief JSON (agent intake schema)")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--k", type=int, default=3, help="number of territories/directions")
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--out", default=None, help="output directory (default: benchmark/runs/<auto>)")
    parser.add_argument("--dry-run", action="store_true", help="render the prompt and exit without calling the API")
    args = parser.parse_args()

    brief = Brief.model_validate(json.loads(Path(args.brief).read_text(encoding="utf-8")))
    system, user = render_prompts(brief, args.k)

    if args.dry_run:
        print("=== SYSTEM ===\n" + system + "\n\n=== USER ===\n" + user)
        schema_fields = list(BaselineOutput.model_fields)
        print(f"\n=== schema: BaselineOutput({', '.join(schema_fields)}) — dry run, no API call ===")
        return 0

    import anthropic  # deferred: --dry-run must work without credentials

    client = anthropic.Anthropic()
    started = time.monotonic()
    response = client.messages.parse(
        model=args.model,
        max_tokens=args.max_tokens,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=BaselineOutput,
    )
    duration = time.monotonic() - started

    if response.stop_reason == "refusal":
        print("request was refused by safety classifiers", file=sys.stderr)
        return 1
    if response.stop_reason == "max_tokens":
        print("hit max_tokens before completing — rerun with a higher --max-tokens", file=sys.stderr)
        return 1
    out: BaselineOutput = response.parsed_output
    if out is None:
        print("model returned no parseable output", file=sys.stderr)
        return 1

    # ---- lift into agent contracts -------------------------------------- #
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"baseline-{stamp}"
    directions: list[Direction] = []
    violations: list[str] = []
    for d in out.directions:
        direction, v = to_agent_direction(run_id, d, args.model)
        directions.append(direction)
        violations.extend(v)

    # divergence, scored by the production service (text-only, same fields)
    settings = get_settings()
    divergence: dict = {"error": "needs >= 2 directions"}
    if len(directions) >= 2:
        report = divergence_report(directions)
        divergence = {
            "min": report["min"],
            "mean": report["mean"],
            "warning": report["warning"],
            "scores": {d.territory.label: report["scores"].get(d.id) for d in directions},
            "embeddings_backend": settings.embeddings_mode,
            "warn_threshold": settings.DIVERGENCE_WARN_MIN,
        }

    # concept package + export.md for the recommended direction, assembled
    # and rendered exactly as the agent's package/export stages do
    by_label = {d.territory.label: d for d in directions}
    recommended = by_label.get(out.recommended_territory_label) or directions[0]
    package = ConceptPackage(
        direction_id=recommended.id,
        territory_label=recommended.territory.label,
        strategy=out.strategy,
        big_idea=recommended.big_idea,
        names=list(out.verbal_identity.names),
        sketches=[],
        art_direction=recommended.art_direction,
        copy=recommended.copy,
        rationale=f"{recommended.big_idea} — {out.strategy.key_message}",
    )
    export_md = render_export_markdown([package], brief.brief)

    # ---- write the run directory ---------------------------------------- #
    out_dir = Path(args.out) if args.out else REPO / "benchmark" / "runs" / f"{Path(args.brief).stem}-{args.model}-{stamp}"
    artifacts = out_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    def dump(path: Path, obj) -> None:
        if hasattr(obj, "model_dump"):
            obj = obj.model_dump()
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    dump(out_dir / "baseline_output.json", out)
    dump(artifacts / "strategy.json", out.strategy)
    dump(artifacts / "verbal_identity.json", out.verbal_identity)
    dump(artifacts / "creative_brief.json", out.creative_brief)
    dump(artifacts / "territories.json", {"territories": [d.territory.model_dump() for d in out.directions]})
    for i, direction in enumerate(directions):
        dump(artifacts / f"direction_{i + 1:02d}.json", direction)
    dump(artifacts / "concept_package.json", package)
    (out_dir / "baseline_export.md").write_text(export_md, encoding="utf-8")

    checks = compliance_checks(out, args.k)
    passed = sum(1 for c in checks if c["passed"])
    dump(
        out_dir / "compliance_report.json",
        {"checks": checks, "passed": f"{passed}/{len(checks)}", "contract_violations": violations, "divergence": divergence},
    )
    dump(
        out_dir / "run_meta.json",
        {
            "brief": str(Path(args.brief)),
            "model": args.model,
            "k": args.k,
            "duration_seconds": round(duration, 1),
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            "stop_reason": response.stop_reason,
            "created_at": stamp,
        },
    )

    print(f"run written to {out_dir.relative_to(REPO)}")
    print(f"  compliance: {passed}/{len(checks)} checks passed; {len(violations)} contract violation(s)")
    if "min" in divergence:
        print(f"  divergence: min={divergence['min']} mean={divergence['mean']} (backend: {divergence['embeddings_backend']})")
    print(f"  tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out; {duration:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
