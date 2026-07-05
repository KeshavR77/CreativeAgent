#!/usr/bin/env python
"""A/B divergence harness CLI (Stage 10, §10 stretch).

Runs the same brief N times per arm and reports how divergent each arm's
direction sets are, using the PRODUCTION divergence metric verbatim:

  * arm ``conceptial``       — the Conceptial ideator      (needs CONCEPTIAL_BASE_URL)
  * arm ``claude_high_temp`` — the plain-Claude baseline   (needs ANTHROPIC_API_KEY)
  * arm ``mock``             — the keyless floor           (always runnable)

Keyless it runs the mock arm only (still emits a valid report); with real keys in
the environment it adds the real arms it has keys for. Writes machine-readable
JSON (``--out``) and prints a human summary.

  python backend/scripts/ab_divergence.py --n 5 --out data/eval/ab.json

Deferred to Keshav (§20): real Conceptial URL/auth; K / warn-threshold tuning.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile

# Explicit env control — never read a stray .env for a measurement run.
os.environ.setdefault("APP_DISABLE_DOTENV", "1")

from app.evaluation.divergence_ab import (  # noqa: E402
    ARM_CLAUDE,
    ARM_CONCEPTIAL,
    ARM_MOCK,
    compare,
    human_summary,
    run_arm,
)
from app.models.artifacts import Brief  # noqa: E402

BRIEF = Brief(
    brief="Launch a sustainable sneaker brand for runners who are sick of greenwashing.",
    audience="runners frustrated by greenwashing",
)

_PROVIDER_KEYS = ("ANTHROPIC_API_KEY", "CONCEPTIAL_BASE_URL", "CONCEPTIAL_API_KEY", "TAVILY_API_KEY")


def _configure_arm(arm: str, ambient: dict) -> bool:
    """Set os.environ so ``arm`` is the ideator in effect. Returns False (skip) if
    the arm needs keys the ambient environment doesn't have."""
    for k in _PROVIDER_KEYS:
        os.environ.pop(k, None)
    os.environ["APP_DISABLE_DOTENV"] = "1"
    os.environ["IMAGE_GEN_PROVIDER"] = "mock"  # keep image lanes cheap + offline
    os.environ["IMAGE_SOURCE_PROVIDER"] = "pexels"

    if arm == ARM_MOCK:
        return True
    if arm == ARM_CLAUDE:
        if not ambient.get("ANTHROPIC_API_KEY"):
            return False
        os.environ["ANTHROPIC_API_KEY"] = ambient["ANTHROPIC_API_KEY"]  # conceptial cleared -> claude fallback
        return True
    if arm == ARM_CONCEPTIAL:
        if not ambient.get("CONCEPTIAL_BASE_URL"):
            return False
        os.environ["CONCEPTIAL_BASE_URL"] = ambient["CONCEPTIAL_BASE_URL"]
        for k in ("CONCEPTIAL_API_KEY", "ANTHROPIC_API_KEY"):  # critic/spine may still be real
            if ambient.get(k):
                os.environ[k] = ambient[k]
        return True
    raise ValueError(f"unknown arm {arm!r}")


def _default_arms(ambient: dict) -> list[str]:
    arms: list[str] = []
    if ambient.get("CONCEPTIAL_BASE_URL"):
        arms.append(ARM_CONCEPTIAL)
    if ambient.get("ANTHROPIC_API_KEY"):
        arms.append(ARM_CLAUDE)
    arms.append(ARM_MOCK)
    return arms


async def _run_arm_isolated(arm: str, n: int, tmpdir: str):
    # Local imports so building storage happens AFTER the arm's env is configured.
    from app.graph.runner import RunManager
    from app.storage.checkpoint import open_checkpointer
    from app.storage.db import init_db, make_engine, make_sessionmaker
    from app.storage.repo import EventBus, EventRepo, RegistryRepo

    engine = make_engine(f"sqlite:///{tmpdir}/app.sqlite")
    init_db(engine)
    sm = make_sessionmaker(engine)
    registry = RegistryRepo(sm)
    bus = EventBus()
    events = EventRepo(sm, bus)
    async with open_checkpointer(f"{tmpdir}/graph.sqlite") as saver:
        rm = RunManager(registry, events, bus, saver)
        return await run_arm(rm, arm, BRIEF, n)


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B divergence harness")
    parser.add_argument("--n", type=int, default=3, help="runs per arm")
    parser.add_argument("--arms", default="", help="comma list; default = arms with available keys + mock")
    parser.add_argument("--out", default="data/eval/ab_divergence.json", help="JSON output path")
    args = parser.parse_args()

    ambient = dict(os.environ)  # capture real keys before we start clearing per-arm
    requested = [a.strip() for a in args.arms.split(",") if a.strip()] or _default_arms(ambient)

    records = []
    for arm in requested:
        if not _configure_arm(arm, ambient):
            print(f"skip arm {arm!r}: required keys not in environment", file=sys.stderr)
            continue
        with tempfile.TemporaryDirectory() as tmpdir:
            records.extend(asyncio.run(_run_arm_isolated(arm, args.n, tmpdir)))

    if not records:
        print("no arms ran (need at least the mock arm)", file=sys.stderr)
        return 1

    comparison = compare(records)
    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(comparison, fh, indent=2)
    print(human_summary(comparison))
    print(f"\nJSON: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
