"""A/B divergence harness tests (Stage 10, §16).

Aggregation math, arm labeling, JSON shape, and the guard that the harness uses
the PRODUCTION divergence metric (no forked pairwise logic). Plus one integration
run of the mock arm through the real graph.
"""

from __future__ import annotations

import json

import pytest

from app.evaluation import divergence_ab as ab
from app.evaluation.divergence_ab import RunRecord
from app.models.artifacts import ArtDirectionSpec, CopyDeck, Direction, Territory
from app.services.divergence import divergence_report


def _dir(did: str, big_idea: str, headline: str, imagery: str, brain: str = "mock") -> Direction:
    return Direction(
        id=did,
        territory=Territory(label="T", lens="lens"),
        big_idea=big_idea,
        brain=brain,
        art_direction=ArtDirectionSpec(imagery_direction=imagery),
        copy=CopyDeck(headline=headline),
        sketches=[],
        status="draft",
    )


def test_harness_uses_production_metric_verbatim() -> None:
    # Guard (§10): the harness imports the production metric, not a forked copy.
    assert ab.divergence_report is divergence_report

    dirs = [
        _dir("d1", "solar joy", "Bright mornings", "sunlit portraits"),
        _dir("d2", "urban grit", "Concrete truth", "gritty rain-slick streets"),
        _dir("d3", "ocean calm", "Go deep", "underwater serenity"),
    ]
    rec = ab.divergence_record(ab.ARM_MOCK, dirs)
    report = divergence_report(dirs)
    assert rec.min == report["min"]
    assert rec.mean == report["mean"]
    assert rec.warning == report["warning"]
    assert rec.n_directions == 3
    assert rec.brains == ["mock", "mock", "mock"]


def test_summarize_arm_aggregation_math() -> None:
    records = [
        RunRecord(arm="mock", min=0.2, mean=0.5, warning=True, n_directions=3, brains=["mock", "mock", "mock"]),
        RunRecord(arm="mock", min=0.4, mean=0.7, warning=False, n_directions=2, brains=["mock", "mock"]),
        RunRecord(arm="other", min=0.9, mean=0.9, warning=False, n_directions=2, brains=["x", "x"]),
    ]
    s = ab.summarize_arm("mock", records)
    assert s.runs == 2
    assert s.mean_min == pytest.approx(0.3)  # (0.2 + 0.4) / 2
    assert s.mean_mean == pytest.approx(0.6)  # (0.5 + 0.7) / 2
    assert s.worst_min == pytest.approx(0.2)  # min(0.2, 0.4)
    assert s.warn_rate == pytest.approx(0.5)  # 1 of 2 warned
    assert s.brain_counts == {"mock": 5}  # 3 + 2; the 'other' arm is ignored


def test_summarize_arm_raises_when_no_runs() -> None:
    with pytest.raises(ValueError):
        ab.summarize_arm("mock", [])


def test_compare_shape_verdict_and_json_serializable() -> None:
    records = [
        # Conceptial diverges MORE (higher mean) than the claude baseline.
        RunRecord(arm=ab.ARM_CONCEPTIAL, min=0.5, mean=0.8, warning=False, n_directions=3, brains=["conceptial"] * 3),
        RunRecord(arm=ab.ARM_CONCEPTIAL, min=0.5, mean=0.8, warning=False, n_directions=3, brains=["conceptial"] * 3),
        RunRecord(arm=ab.ARM_CLAUDE, min=0.2, mean=0.4, warning=True, n_directions=3, brains=["claude_high_temp"] * 3),
        RunRecord(arm=ab.ARM_CLAUDE, min=0.2, mean=0.4, warning=True, n_directions=3, brains=["claude_high_temp"] * 3),
    ]
    out = ab.compare(records)
    assert set(out["arms"]) == {ab.ARM_CONCEPTIAL, ab.ARM_CLAUDE}
    assert out["arms"][ab.ARM_CLAUDE]["warn_rate"] == pytest.approx(1.0)
    v = out["verdict"]
    assert v["treatment"] == ab.ARM_CONCEPTIAL and v["baseline"] == ab.ARM_CLAUDE
    assert v["treatment_more_divergent"] is True
    assert v["mean_divergence_delta"] == pytest.approx(0.4)  # 0.8 - 0.4
    json.dumps(out)  # machine-readable output


def test_human_summary_mentions_arms_and_verdict() -> None:
    records = [
        RunRecord(arm=ab.ARM_CONCEPTIAL, min=0.5, mean=0.8, warning=False, n_directions=3, brains=["conceptial"] * 3),
        RunRecord(arm=ab.ARM_CLAUDE, min=0.2, mean=0.4, warning=True, n_directions=3, brains=["claude_high_temp"] * 3),
    ]
    text = ab.human_summary(ab.compare(records))
    assert ab.ARM_CONCEPTIAL in text and ab.ARM_CLAUDE in text
    assert "Verdict" in text


async def test_run_arm_mock_through_graph(graph_manager, sneaker_brief) -> None:
    run_manager, _registry = graph_manager
    records = await ab.run_arm(run_manager, ab.ARM_MOCK, sneaker_brief, 2)
    assert len(records) == 2
    for r in records:
        assert r.arm == ab.ARM_MOCK
        assert r.n_directions >= 3
        assert set(r.brains) == {"mock"}  # keyless -> the mock ideator


async def test_run_arm_skips_runs_with_fewer_than_two_directions() -> None:
    """A run that lost territories (<2 active) is undefined for divergence — the
    harness must skip it, not crash on the ValueError from divergence_report."""
    from types import SimpleNamespace

    class _StubRM:
        def __init__(self, directions):
            self._dirs = directions

        async def start(self, pid, brief):
            async def _noop():
                return None

            return _noop()

        async def resume(self, pid, decision):
            async def _noop():
                return None

            return _noop()

        async def get_view(self, pid):
            return SimpleNamespace(directions=self._dirs)

    solo = [_dir("solo", "only idea", "Head", "img")]  # one active direction
    records = await ab.run_arm(_StubRM(solo), ab.ARM_MOCK, "brief", 2)
    assert records == []  # both runs skipped, no exception
