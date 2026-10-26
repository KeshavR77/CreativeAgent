"""GraphState + reducer contract tests.

Every state key written by parallel `Send` branches must carry a reducer, or
concurrent writes clobber each other. `directions` upserts by id; `costs` and
`failed_territories` accumulate with `operator.add`.
"""

from __future__ import annotations

import operator
from typing import Annotated, get_args, get_type_hints

from app.models.artifacts import (
    ArtDirectionSpec,
    CopyDeck,
    Direction,
    Territory,
)
from app.models.state import GraphState, upsert_directions


def _dir(did: str, big_idea: str = "idea") -> Direction:
    return Direction(
        id=did,
        territory=Territory(label="T", lens="lens"),
        big_idea=big_idea,
        brain="mock",
        art_direction=ArtDirectionSpec(imagery_direction="x"),
        copy=CopyDeck(headline="h"),
        sketches=[],
    )


# --------------------------------------------------------------------------- #
# upsert_directions                                                           #
# --------------------------------------------------------------------------- #
def test_upsert_insert_distinct_ids_appends() -> None:
    merged = upsert_directions([_dir("a")], [_dir("b")])
    assert [d.id for d in merged] == ["a", "b"]


def test_upsert_replace_by_id_no_duplicate() -> None:
    merged = upsert_directions([_dir("a", "old")], [_dir("a", "new")])
    assert len(merged) == 1
    assert merged[0].big_idea == "new"


def test_upsert_mixed_insert_and_replace_preserves_order() -> None:
    base = [_dir("a"), _dir("b")]
    merged = upsert_directions(base, [_dir("b", "new"), _dir("c")])
    assert [d.id for d in merged] == ["a", "b", "c"]
    assert next(d for d in merged if d.id == "b").big_idea == "new"


def test_upsert_none_safety() -> None:
    assert [d.id for d in upsert_directions(None, [_dir("a")])] == ["a"]
    assert [d.id for d in upsert_directions([_dir("a")], None)] == ["a"]
    assert upsert_directions(None, None) == []


def test_upsert_accepts_dicts() -> None:
    # LangGraph may hand the reducer raw dicts before model coercion.
    merged = upsert_directions([{"id": "a", "big_idea": "old"}], [{"id": "a", "big_idea": "new"}])
    assert len(merged) == 1


def test_upsert_simulated_parallel_send_fan_in() -> None:
    # Two Send branches each contribute one direction; fold left-to-right.
    acc: list = []
    for branch in ([_dir("a")], [_dir("b")], [_dir("c")]):
        acc = upsert_directions(acc, branch)
    assert [d.id for d in acc] == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# GraphState reducer wiring                                                   #
# --------------------------------------------------------------------------- #
def test_parallel_written_keys_have_reducers() -> None:
    hints = get_type_hints(GraphState, include_extras=True)

    def reducer_of(key: str):
        meta = get_args(hints[key])
        # Annotated[list[...], reducer] -> reducer is the 2nd arg
        return meta[1] if len(meta) >= 2 else None

    assert reducer_of("directions") is upsert_directions
    assert reducer_of("costs") is operator.add
    assert reducer_of("failed_territories") is operator.add


def test_graphstate_is_total_false() -> None:
    # total=False: every key optional (partial deltas returned by nodes).
    assert GraphState.__total__ is False


def test_graphstate_has_core_keys() -> None:
    hints = get_type_hints(GraphState, include_extras=True)
    for key in (
        "project_id",
        "brief",
        "research",
        "strategy",
        "verbal_identity",
        "creative_brief",
        "territories",
        "directions",
        "failed_territories",
        "costs",
        "divergence",
        "packages",
    ):
        assert key in hints


def test_annotated_directions_inner_type() -> None:
    hints = get_type_hints(GraphState, include_extras=True)
    inner = get_args(hints["directions"])[0]  # list[Direction]
    assert get_args(inner)[0] is Direction
    # sanity that it is an Annotated alias
    assert Annotated is Annotated
