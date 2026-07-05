"""Divergence engine tests (Stage 04, §11/§16).

Pairwise cosine distance over each direction's DIVERGENCE_FIELDS text
(big_idea + copy.headline + art_direction.imagery_direction). Warning when the
minimum pair distance drops below DIVERGENCE_WARN_MIN. Killed/merged_away
directions are excluded; fewer than two active directions raises.
"""

from __future__ import annotations

import math

import pytest

from app.models.artifacts import ArtDirectionSpec, CopyDeck, Direction, Territory
from app.services.divergence import (
    cosine_distance,
    compute_divergence,
    divergence_report,
)


def _dir(did: str, big_idea: str, headline: str, imagery: str, status: str = "draft") -> Direction:
    return Direction(
        id=did,
        territory=Territory(label="T", lens="lens"),
        big_idea=big_idea,
        brain="mock",
        art_direction=ArtDirectionSpec(imagery_direction=imagery),
        copy=CopyDeck(headline=headline),
        sketches=[],
        status=status,
    )


# --------------------------------------------------------------------------- #
# cosine + compute_divergence over KNOWN vectors -> exact min/mean            #
# --------------------------------------------------------------------------- #
def test_cosine_distance_basics() -> None:
    assert cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)
    assert cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)
    # zero vector -> maximal distance (no direction)
    assert cosine_distance([0.0, 0.0], [1.0, 1.0]) == pytest.approx(1.0)


def test_compute_divergence_known_vectors_exact() -> None:
    result = compute_divergence([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    near = 1.0 - 1.0 / math.sqrt(2)  # ~0.29289
    assert result["min"] == pytest.approx(near, abs=1e-9)
    assert result["mean"] == pytest.approx((1.0 + near + near) / 3, abs=1e-9)


def test_compute_divergence_requires_two_vectors() -> None:
    with pytest.raises(ValueError):
        compute_divergence([[1.0, 0.0]])


# --------------------------------------------------------------------------- #
# divergence_report over directions (mock embeddings)                        #
# --------------------------------------------------------------------------- #
def test_report_warns_on_near_identical(clean_env) -> None:
    dirs = [
        _dir("a", "same idea", "same head", "same imagery"),
        _dir("b", "same idea", "same head", "same imagery"),
    ]
    rep = divergence_report(dirs)
    assert rep["min"] == pytest.approx(0.0, abs=1e-9)
    assert rep["warning"] is True
    assert set(rep["scores"]) == {"a", "b"}


def test_report_no_warning_on_distinct(clean_env) -> None:
    dirs = [
        _dir("a", "running proof honest", "trail dawn", "earthy grounded muted"),
        _dir("b", "luxury gold shine", "city night", "sleek chrome polished"),
    ]
    rep = divergence_report(dirs)
    assert rep["warning"] is False  # disjoint tokens -> distance ~1.0 >= 0.15


def test_report_excludes_killed_and_merged_away(clean_env) -> None:
    dirs = [
        _dir("a", "alpha", "alpha", "alpha"),
        _dir("b", "beta", "beta", "beta", status="killed"),
        _dir("c", "gamma", "gamma", "gamma", status="merged_away"),
        _dir("d", "delta", "delta", "delta"),
    ]
    rep = divergence_report(dirs)
    assert set(rep["scores"]) == {"a", "d"}  # only active directions scored


def test_report_requires_two_active(clean_env) -> None:
    dirs = [
        _dir("a", "alpha", "alpha", "alpha"),
        _dir("b", "beta", "beta", "beta", status="killed"),
    ]
    with pytest.raises(ValueError):
        divergence_report(dirs)


def test_report_warning_threshold_respects_config(clean_env) -> None:
    # identical -> min 0; a threshold of 0 must NOT warn (0 < 0 is False).
    clean_env.setenv("DIVERGENCE_WARN_MIN", "0.0")
    dirs = [_dir("a", "x", "x", "x"), _dir("b", "x", "x", "x")]
    assert divergence_report(dirs)["warning"] is False
