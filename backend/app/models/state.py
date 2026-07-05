"""Graph state + reducers (§6.2).

`GraphState` is the LangGraph channel schema. Every key written by parallel
`Send` branches carries a reducer so concurrent writes merge instead of clobber:
`directions` upserts by id, while `costs` and `failed_territories` accumulate
with `operator.add`.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict, Union

from app.models.artifacts import (
    Brief,
    ConceptPackage,
    CostRecord,
    CreativeBrief,
    Direction,
    ResearchDossier,
    Strategy,
    Territory,
    VerbalIdentity,
)

# A direction may reach the reducer as a model or as a raw dict (pre-coercion).
DirectionLike = Union[Direction, dict]


def _direction_id(d: DirectionLike) -> Any:
    return d["id"] if isinstance(d, dict) else d.id


def upsert_directions(
    left: Optional[list[DirectionLike]],
    right: Optional[list[DirectionLike]],
) -> list[DirectionLike]:
    """Merge direction lists by id.

    Existing entries with a matching id are *replaced* (last write wins);
    new ids are appended in arrival order. This makes parallel `Send` fan-in
    and single-direction updates (edit/regenerate/critique) safe and idempotent.
    """
    merged: list[DirectionLike] = list(left) if left else []
    if not right:
        return merged
    index = {_direction_id(d): i for i, d in enumerate(merged)}
    updates = right if isinstance(right, list) else [right]
    for d in updates:
        key = _direction_id(d)
        if key in index:
            merged[index[key]] = d
        else:
            index[key] = len(merged)
            merged.append(d)
    return merged


class GraphState(TypedDict, total=False):
    """LangGraph channel schema. `total=False`: nodes return partial deltas."""

    project_id: str
    brief: Brief
    clarifying_answers: list[str]
    research: ResearchDossier
    strategy: Strategy
    rejection_notes: str
    edited_by_human: bool
    verbal_identity: VerbalIdentity
    creative_brief: CreativeBrief
    territories: list[Territory]
    # keys written by parallel Send branches — each MUST carry a reducer.
    directions: Annotated[list[Direction], upsert_directions]
    failed_territories: Annotated[list[str], operator.add]
    costs: Annotated[list[CostRecord], operator.add]
    # fan-in results
    divergence: dict
    packages: list[ConceptPackage]
