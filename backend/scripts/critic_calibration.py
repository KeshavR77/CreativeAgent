#!/usr/bin/env python
"""Critic calibration harness CLI.

Drives N runs to Gate 2, collects the critic's rubric scores + verdicts, appends
them to an accumulating JSONL dataset, then reports score distributions per
criterion, verdict base rates, and generator->critic model pairings — the
evidence for tuning the ship/revise/kill thresholds.

  python backend/scripts/critic_calibration.py --n 5           # add 5 runs, summarize
  python backend/scripts/critic_calibration.py --summarize-only # just summarize the dataset

Keyless it uses the mock ideator + mock critic, whose scores are deterministic
fixtures — a keyless dataset says nothing about a real critic's calibration. With
real keys the accumulated dataset reflects the real generator/critic pairing.

Unresolved: the persisted data-collection format. The JSONL store here is a
working default only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile

os.environ.setdefault("APP_DISABLE_DOTENV", "1")

from app.evaluation.calibration import (  # noqa: E402
    append_samples,
    collect_samples,
    load_samples,
    summarize_calibration,
)
from app.models.artifacts import Brief  # noqa: E402

BRIEF = Brief(
    brief="Launch a sustainable sneaker brand for runners who are sick of greenwashing.",
    audience="runners frustrated by greenwashing",
)


async def _collect_runs(n: int, tmpdir: str):
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
        views = []
        for i in range(n):
            pid = f"cal-{i}"
            await (await rm.start(pid, BRIEF))
            await (await rm.resume(pid, {"action": "approve"}))
            views.append(await rm.get_view(pid))
        return collect_samples(views)


def main() -> int:
    parser = argparse.ArgumentParser(description="Critic calibration harness")
    parser.add_argument("--n", type=int, default=3, help="runs to add to the dataset")
    parser.add_argument("--data", default="data/eval/critiques.jsonl", help="accumulating JSONL dataset")
    parser.add_argument("--out", default="data/eval/calibration.json", help="summary JSON output")
    parser.add_argument("--summarize-only", action="store_true", help="skip runs; summarize the dataset as-is")
    args = parser.parse_args()

    if not args.summarize_only:
        # Mock-first: no keys, image lanes cheap/offline.
        os.environ["IMAGE_GEN_PROVIDER"] = "mock"
        os.environ["IMAGE_SOURCE_PROVIDER"] = "pexels"
        with tempfile.TemporaryDirectory() as tmpdir:
            new = asyncio.run(_collect_runs(args.n, tmpdir))
        added = append_samples(args.data, new)
        print(f"added {added} critique sample(s) from {args.n} run(s) -> {args.data}")

    samples = load_samples(args.data)
    if not samples:
        print("no critique data yet (run without --summarize-only first)", file=sys.stderr)
        return 1

    summary = summarize_calibration(samples)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\ncalibration over {summary['n']} sample(s):")
    print("  verdict base rates :", summary["verdict_base_rates"])
    print("  model pairings     :", summary["model_pairings"])
    for crit, dist in summary["per_criterion"].items():
        print(f"  {crit:20s}: mean={dist['mean']} hist={dist['histogram']}")
    print(f"\nJSON: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
