"""Baseline benchmark: one Claude API call standing in for the whole agent pipeline.

Feeds the same intake `Brief` JSON the agent receives to a single streaming
Messages API call whose prompt (benchmark/baseline_prompt.md) targets the
research + ideation report spec in benchmark/baseline_output_spec.md. The
output is a free-form markdown report — the deliverable both systems are
scored against with the same rubric. This stays a *baseline*: one prompt, one
call, no tools, no retrieval, no orchestration.

Usage (from the repo root; needs ANTHROPIC_API_KEY or an `ant auth login`
profile):

    backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/nutrition.json
    backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/sneaker.json \
        --model claude-sonnet-4-5 --no-thinking
    backend/.venv/bin/python benchmark/run_baseline.py benchmark/briefs/nutrition.json --dry-run

Pass `--model` matching the agent's CLAUDE_MODEL to isolate architecture from
model capability. Models older than the 4.6 family (e.g. claude-sonnet-4-5)
reject adaptive thinking — pass --no-thinking for those.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from app.models.artifacts import Brief  # noqa: E402  (input parity with the agent)


def render_prompts(brief: Brief) -> tuple[str, str]:
    template = (REPO / "benchmark" / "baseline_prompt.md").read_text(encoding="utf-8")
    # anchor on the headings at line start (the intro prose mentions them inline)
    _, system_and_user = template.split("\n## System\n", 1)
    system, user = system_and_user.split("\n## User\n", 1)
    values = {
        "brief": brief.brief,
        "brand_name": brief.brand_name or "(unnamed — naming is out of scope; refer to 'the brand')",
        "audience": brief.audience or "(not specified)",
        "constraints": "\n".join(f"- {c}" for c in brief.constraints) or "- (none)",
    }
    for key, value in values.items():
        system = system.replace(f"{{{{{key}}}}}", value)
        user = user.replace(f"{{{{{key}}}}}", value)
    return system.strip(), user.strip()


# The mechanically checkable subset of baseline_output_spec.md. The full rubric
# needs a human (or LLM-judge) read; these checks only catch structural misses.
REQUIRED_SECTIONS = [
    "## 1. Competitive & Category Audit",
    "## 2. Category Codes",
    "## 3. Audience Insight Brief",
    "## 4. White-Space Maps",
    "## 5. Positioning Territories",
    "## 6. Draft Messaging & Brand Architecture Scaffold",
    "## 7. Creative Springboards",
]


def conformance_checks(report: str) -> list[dict]:
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    positions = [report.find(h) for h in REQUIRED_SECTIONS]
    for heading, pos in zip(REQUIRED_SECTIONS, positions):
        check(f"section present: {heading}", pos != -1)
    found = [p for p in positions if p != -1]
    check("sections appear in spec order", found == sorted(found))

    territories = len(re.findall(r"^### Territory \d+", report, flags=re.MULTILINE))
    check("3–5 positioning territories", 3 <= territories <= 5, f"{territories} found")
    maps = len(re.findall(r"^### Map \d+", report, flags=re.MULTILINE))
    check("2–3 white-space maps", 2 <= maps <= 3, f"{maps} found")

    verify_tags = report.count("[verify]")
    check(
        "unsourced factual claims are tagged [verify]",
        verify_tags >= 1,
        f"{verify_tags} tags (no retrieval available, so >=1 expected)",
    )
    confidence = len(re.findall(r"confidence", report, flags=re.IGNORECASE))
    check("confidence flags present", confidence >= 3, f"{confidence} mentions")
    check("messaging scaffold marked DRAFT", "DRAFT" in report)
    check("brief reframe present", re.search(r"reframe", report, re.IGNORECASE) is not None)
    check(
        "no fabricated citations (no URLs — baseline has no retrieval)",
        "http://" not in report and "https://" not in report,
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", help="path to a Brief JSON (agent intake schema)")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=32000,
        help="output budget shared by thinking + report (default 32000)",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="omit adaptive thinking (required for pre-4.6 models like claude-sonnet-4-5)",
    )
    parser.add_argument("--out", default=None, help="output directory (default: benchmark/runs/<auto>)")
    parser.add_argument("--dry-run", action="store_true", help="render the prompt and exit without calling the API")
    args = parser.parse_args()

    brief = Brief.model_validate(json.loads(Path(args.brief).read_text(encoding="utf-8")))
    system, user = render_prompts(brief)

    if args.dry_run:
        print("=== SYSTEM ===\n" + system + "\n\n=== USER ===\n" + user)
        print("\n=== free-form markdown report; no API call made ===")
        return 0

    import anthropic  # deferred: --dry-run must work without credentials

    client = anthropic.Anthropic()
    request: dict = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if not args.no_thinking:
        request["thinking"] = {"type": "adaptive"}

    started = time.monotonic()
    # streamed: a full multi-section report can exceed non-streaming timeouts
    with client.messages.stream(**request) as stream:
        response = stream.get_final_message()
    duration = time.monotonic() - started

    if response.stop_reason == "refusal":
        print("request was refused by safety classifiers", file=sys.stderr)
        return 1
    report = "".join(block.text for block in response.content if block.type == "text")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) if args.out else REPO / "benchmark" / "runs" / f"{Path(args.brief).stem}-{args.model}-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "report.md").write_text(report, encoding="utf-8")
    checks = conformance_checks(report)
    passed = sum(1 for c in checks if c["passed"])
    (out_dir / "conformance_report.json").write_text(
        json.dumps({"checks": checks, "passed": f"{passed}/{len(checks)}"}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "brief": str(Path(args.brief)),
                "model": args.model,
                "max_tokens": args.max_tokens,
                "thinking": "adaptive" if not args.no_thinking else "off",
                "duration_seconds": round(duration, 1),
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                "stop_reason": response.stop_reason,
                "created_at": stamp,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"run written to {out_dir.relative_to(REPO)}")
    print(f"  structural conformance: {passed}/{len(checks)} checks passed (full rubric: baseline_output_spec.md)")
    print(f"  tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out; {duration:.0f}s")
    if response.stop_reason == "max_tokens":
        print("  WARNING: hit max_tokens — report is truncated; rerun with a higher --max-tokens", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
