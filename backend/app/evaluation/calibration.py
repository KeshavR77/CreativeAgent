"""Critic calibration harness (Stage 10, §10 stretch).

Accumulates the critic's rubric scores + verdicts across runs so the
``ship``/``revise``/``kill`` thresholds and generator-vs-critic pairings can be
tuned with evidence. Pure collection/aggregation + a JSONL store here; the
runnable CLI is ``scripts/critic_calibration.py``.

TODO(§20 — Keshav): the persisted data-collection FORMAT (exact fields, storage
backend, provenance/PII policy) is Keshav's call. The JSONL store below is a
working default only — do not treat it as the final schema.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

# The five rubric criteria the critic scores (CritiqueScore, §6.1).
CRITERIA = ("distinctiveness", "strategic_fit", "memorability", "audience_resonance", "feasibility")


@dataclass
class CritiqueSample:
    verdict: str
    scores: dict[str, int]
    generator_model: str  # the ``brain`` that produced the direction
    critic_model: str


def collect_samples(views) -> list[CritiqueSample]:
    """Extract one CritiqueSample per critiqued direction across project views."""
    samples: list[CritiqueSample] = []
    for view in views:
        for d in getattr(view, "directions", None) or []:
            critique = getattr(d, "critique", None)
            if critique is None:
                continue
            samples.append(
                CritiqueSample(
                    verdict=critique.verdict,
                    scores={c: getattr(critique, c) for c in CRITERIA},
                    generator_model=getattr(d, "brain", "?"),
                    critic_model=getattr(critique, "critic_model", "?"),
                )
            )
    return samples


def _distribution(values: list[int]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "min": None, "max": None, "histogram": {}}
    hist: dict[int, int] = {}
    for v in values:
        hist[v] = hist.get(v, 0) + 1
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "histogram": {str(k): hist[k] for k in sorted(hist)},
    }


def _counts(labels: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in labels:
        out[x] = out.get(x, 0) + 1
    # most frequent first, ties broken alphabetically
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def summarize_calibration(samples) -> dict:
    """Score distribution per criterion, verdict base rates, and generator->critic
    model pairings — the evidence for tuning thresholds."""
    samples = list(samples)
    per_criterion = {
        c: _distribution([s.scores[c] for s in samples if c in s.scores]) for c in CRITERIA
    }
    return {
        "n": len(samples),
        "per_criterion": per_criterion,
        "verdict_base_rates": _counts([s.verdict for s in samples]),
        "model_pairings": _counts([f"{s.generator_model}->{s.critic_model}" for s in samples]),
    }


# --------------------------------------------------------------------------- #
# JSONL store (working-default format — see the module TODO)                   #
# --------------------------------------------------------------------------- #
def append_samples(path, samples) -> int:
    """Append samples to a JSONL dataset (accumulates across runs). Returns count."""
    samples = list(samples)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(asdict(s)) + "\n")
    return len(samples)


def load_samples(path) -> list[CritiqueSample]:
    """Load an accumulated JSONL dataset back into CritiqueSamples."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[CritiqueSample] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(CritiqueSample(**json.loads(line)))
    return out
