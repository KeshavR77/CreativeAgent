"""Critic calibration harness tests.

Sample collection from project views, aggregation math (score distributions,
verdict base rates, model pairings), JSON shape, and the JSONL store that
accumulates critique data across runs.
"""

from __future__ import annotations

import json

import pytest

from app.evaluation import calibration as cal
from app.evaluation.calibration import CritiqueSample
from app.models.artifacts import ArtDirectionSpec, CopyDeck, CritiqueScore, Direction, Territory

# case_against must be >= 50 words (model invariant).
_CASE = " ".join(["against"] * 55)


def _crit(verdict: str, d: int, s: int, m: int, a: int, f: int, critic_model: str = "mock-critic") -> CritiqueScore:
    return CritiqueScore(
        distinctiveness=d,
        strategic_fit=s,
        memorability=m,
        audience_resonance=a,
        feasibility=f,
        case_against=_CASE,
        verdict=verdict,
        critic_model=critic_model,
    )


def _dir(did: str, brain: str, critique) -> Direction:
    return Direction(
        id=did,
        territory=Territory(label="T", lens="l"),
        big_idea="idea",
        brain=brain,
        art_direction=ArtDirectionSpec(imagery_direction="img"),
        copy=CopyDeck(headline="h"),
        sketches=[],
        critique=critique,
        status="draft",
    )


class _View:
    def __init__(self, directions):
        self.directions = directions


def test_collect_samples_skips_uncritiqued() -> None:
    views = [
        _View(
            [
                _dir("d1", "external_ideator", _crit("ship", 5, 4, 5, 4, 5)),
                _dir("d2", "mock", None),  # not yet critiqued -> skipped
            ]
        ),
        _View([_dir("d3", "claude_high_temp", _crit("kill", 2, 2, 1, 2, 3))]),
    ]
    samples = cal.collect_samples(views)
    assert len(samples) == 2
    assert {s.verdict for s in samples} == {"ship", "kill"}
    assert samples[0].scores["distinctiveness"] == 5
    assert samples[0].generator_model == "external_ideator"
    assert samples[0].critic_model == "mock-critic"


def test_summarize_calibration_math_and_json() -> None:
    samples = [
        CritiqueSample("ship", {"distinctiveness": 5, "strategic_fit": 4, "memorability": 5, "audience_resonance": 4, "feasibility": 5}, "external_ideator", "mock-critic"),
        CritiqueSample("kill", {"distinctiveness": 1, "strategic_fit": 2, "memorability": 1, "audience_resonance": 2, "feasibility": 3}, "external_ideator", "mock-critic"),
        CritiqueSample("ship", {"distinctiveness": 3, "strategic_fit": 3, "memorability": 3, "audience_resonance": 3, "feasibility": 3}, "claude_high_temp", "mock-critic"),
    ]
    summary = cal.summarize_calibration(samples)
    assert summary["n"] == 3

    dist = summary["per_criterion"]["distinctiveness"]
    assert dist["n"] == 3
    assert dist["mean"] == pytest.approx((5 + 1 + 3) / 3)
    assert dist["min"] == 1 and dist["max"] == 5
    assert dist["histogram"] == {"1": 1, "3": 1, "5": 1}

    assert summary["verdict_base_rates"] == {"ship": 2, "kill": 1}
    assert summary["model_pairings"]["external_ideator->mock-critic"] == 2
    json.dumps(summary)  # machine-readable


def test_jsonl_store_accumulates_across_runs(tmp_path) -> None:
    path = tmp_path / "eval" / "critiques.jsonl"
    s1 = [CritiqueSample("ship", {c: 4 for c in cal.CRITERIA}, "external_ideator", "mock-critic")]
    s2 = [CritiqueSample("kill", {c: 2 for c in cal.CRITERIA}, "mock", "mock-critic")]

    assert cal.append_samples(path, s1) == 1
    assert cal.append_samples(path, s2) == 1  # second run appends, does not overwrite

    loaded = cal.load_samples(path)
    assert len(loaded) == 2
    assert {s.verdict for s in loaded} == {"ship", "kill"}
    assert cal.summarize_calibration(loaded)["n"] == 2


def test_load_missing_dataset_is_empty(tmp_path) -> None:
    assert cal.load_samples(tmp_path / "nope.jsonl") == []
