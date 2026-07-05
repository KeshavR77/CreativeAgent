"""Divergence engine (§11).

Measures how distinct a set of directions are from one another via pairwise
cosine distance over their DIVERGENCE_FIELDS text (text-only by design — never
fed image data). Emits an overall {min, mean, warning} plus a per-direction
nearest-neighbour score. Killed/merged_away directions are excluded; fewer than
two active directions is an error (divergence is undefined for one concept).
"""

from __future__ import annotations

import math
from typing import Iterable

from app.config import get_settings
from app.models.artifacts import DIVERGENCE_FIELDS
from app.services.embeddings import embed

# statuses whose directions do not participate in divergence.
_EXCLUDED_STATUSES = frozenset({"killed", "merged_away"})


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity. A zero vector has no direction -> distance 1.0."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    return 1.0 - dot / (na * nb)


def _pairwise(vectors: list[list[float]]) -> list[float]:
    n = len(vectors)
    return [
        cosine_distance(vectors[i], vectors[j])
        for i in range(n)
        for j in range(i + 1, n)
    ]


def compute_divergence(vectors: list[list[float]]) -> dict:
    """Overall {min, mean} pairwise distance. Requires >= 2 vectors."""
    if len(vectors) < 2:
        raise ValueError("divergence requires at least two vectors")
    dists = _pairwise(vectors)
    return {"min": min(dists), "mean": sum(dists) / len(dists)}


def direction_text(direction) -> str:
    """Concatenate a direction's DIVERGENCE_FIELDS (dotted paths) into one text."""
    parts: list[str] = []
    for field in DIVERGENCE_FIELDS:
        obj = direction
        for attr in field.split("."):
            obj = getattr(obj, attr)
        parts.append(str(obj))
    return " ".join(parts)


def active_directions(directions: Iterable) -> list:
    return [d for d in directions if d.status not in _EXCLUDED_STATUSES]


def divergence_report(directions: Iterable) -> dict:
    """Full report over the ACTIVE directions.

    Returns {min, mean, warning, scores} where ``scores`` maps direction id ->
    its nearest-neighbour distance (higher = more distinct). ``warning`` is True
    when the minimum pair distance is strictly below ``DIVERGENCE_WARN_MIN``.
    """
    active = active_directions(directions)
    if len(active) < 2:
        raise ValueError("divergence requires at least two active directions")
    vectors = embed([direction_text(d) for d in active])
    overall = compute_divergence(vectors)
    scores = {
        d.id: min(
            cosine_distance(vectors[i], vectors[j])
            for j in range(len(active))
            if j != i
        )
        for i, d in enumerate(active)
    }
    warn_min = get_settings().DIVERGENCE_WARN_MIN
    return {
        "min": overall["min"],
        "mean": overall["mean"],
        "warning": overall["min"] < warn_min,
        "scores": scores,
    }
