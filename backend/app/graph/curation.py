"""Gate 2 — the curation gate and its full op table (§9.4/§12.2).

``curation_gate`` interrupts (first statement) surfacing the directions +
divergence, then routes on the operator's op. Every op is applied inline after
the interrupt and routes back through ordinary graph edges (no side-job queue):

  promote / kill / annotate      -> self-loop (re-interrupt)
  edit                           -> divergence-field? divergence : self-loop; critique_stale
  regenerate_field               -> (same routing) regenerate one field; critique_stale
  recritique                     -> re-critique (clears staleness) -> divergence
  fork                           -> child (parent_id, lens_tweak) -> critique -> divergence
  merge                          -> merged (merged_from; parents merged_away) -> critique -> divergence
  finalize                       -> requires >=1 promoted -> refine / package

The regenerate/fork/merge/recritique steps reuse the exploration inner helpers
(so the critic stays independent and `brain` truthful).
"""

from __future__ import annotations

from langgraph.config import get_stream_writer
from langgraph.types import Command, interrupt

from app.config import get_settings
from app.graph import exploration
from app.models.artifacts import (
    DIVERGENCE_FIELDS,
    EDITABLE_FIELDS,
    Annotation,
    Direction,
)
from app.models.events import DirectionChange, EventType
from app.models.state import GraphState

_GATE = "curation_gate"
_DIVERGENCE = "divergence"


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _by_id(directions: list, direction_id: str):
    for d in directions:
        if d.id == direction_id:
            return d
    return None


def _summary(d: Direction) -> dict:
    return {
        "id": d.id,
        "big_idea": d.big_idea,
        "headline": d.copy.headline,
        "brain": d.brain,
        "status": d.status,
        "critique_stale": d.critique_stale,
        "divergence_score": d.divergence_score,
        "critique": d.critique.model_dump() if d.critique is not None else None,
        "annotations": [a.model_dump() for a in d.annotations],
        "parent_id": d.parent_id,
        "merged_from": list(d.merged_from),
    }


def _get_field(d: Direction, field: str):
    obj = d
    for part in field.split("."):
        obj = getattr(obj, part)
    return obj


def _set_field(d: Direction, field: str, value) -> Direction:
    """Return a copy of `d` with `field` (1- or 2-level dotted) set, marking the
    critique stale."""
    updates: dict = {"critique_stale": True}
    if "." in field:
        parent, child = field.split(".", 1)
        sub = getattr(d, parent)
        updates[parent] = sub.model_copy(update={child: value})
    else:
        updates[field] = value
    return d.model_copy(update=updates)


def _route_after_field_change(field: str) -> str:
    return _DIVERGENCE if field in DIVERGENCE_FIELDS else _GATE


# --------------------------------------------------------------------------- #
# the gate                                                                     #
# --------------------------------------------------------------------------- #
def curation_gate(state: GraphState) -> Command:
    directions = state.get("directions", [])
    project_id = state.get("project_id", "")
    op = interrupt(
        {
            "gate": "curation",
            "directions": [_summary(d) for d in directions],
            "divergence": state.get("divergence"),
        }
    )
    kind = op.get("op")

    if kind == "promote":
        return _set_status(directions, op["direction_id"], "promoted")
    if kind == "kill":
        return _set_status(directions, op["direction_id"], "killed")
    if kind == "annotate":
        return _annotate(directions, op["direction_id"], op.get("text", ""), op.get("author", "human"))
    if kind == "edit":
        return _apply_edit(directions, op)
    if kind == "regenerate_field":
        return _regenerate_field(project_id, directions, op)
    if kind == "recritique":
        return _recritique(project_id, directions, op)
    if kind == "fork":
        return _fork(project_id, directions, op)
    if kind == "merge":
        return _merge(project_id, directions, op)
    if kind == "regenerate_sketch":
        return _regenerate_sketch(project_id, directions, op)
    if kind == "regenerate_sketches":
        return _regenerate_sketches(project_id, directions, op)
    if kind == "regenerate_moodboard_item":
        return _regenerate_moodboard_item(project_id, directions, op)
    if kind == "finalize":
        return _finalize(directions, op)
    # unknown op -> safe self-loop (still awaiting curation)
    return Command(goto=_GATE)


# --------------------------------------------------------------------------- #
# ops                                                                          #
# --------------------------------------------------------------------------- #
def _set_status(directions: list, direction_id: str, status: str) -> Command:
    d = _by_id(directions, direction_id)
    if d is None:
        return Command(goto=_GATE)
    return Command(goto=_GATE, update={"directions": [d.model_copy(update={"status": status})]})


def _annotate(directions: list, direction_id: str, text: str, author: str) -> Command:
    d = _by_id(directions, direction_id)
    if d is None:
        return Command(goto=_GATE)
    annotations = list(d.annotations) + [Annotation(text=text, author=author)]
    return Command(goto=_GATE, update={"directions": [d.model_copy(update={"annotations": annotations})]})


def _emit_updated(direction_id: str, change: DirectionChange) -> None:
    get_stream_writer()(
        {"type": EventType.direction_updated.value, "direction_id": direction_id, "change": change.value}
    )


def _apply_edit(directions: list, op: dict) -> Command:
    d = _by_id(directions, op["direction_id"])
    field = op.get("field", "")
    if d is None or field not in EDITABLE_FIELDS:
        return Command(goto=_GATE)
    updated = _set_field(d, field, op.get("value"))
    _emit_updated(d.id, DirectionChange.edit)
    return Command(goto=_route_after_field_change(field), update={"directions": [updated]})


def _regenerate_spec_field(project_id: str, d: Direction, field: str):
    art, copy = exploration.build_spec(project_id, d.territory, d.big_idea)
    source = {"copy": copy, "art_direction": art}
    parent, child = field.split(".", 1)
    return getattr(source[parent], child)


def _regenerate_field(project_id: str, directions: list, op: dict) -> Command:
    d = _by_id(directions, op["direction_id"])
    field = op.get("field", "")
    if d is None or field not in EDITABLE_FIELDS:
        return Command(goto=_GATE)
    if field == "big_idea":
        # A regenerated big_idea may come from a different ideator — keep `brain`
        # truthful to the model that produced the value now on the card.
        big_idea, brain = exploration.ideate_one(project_id, d.territory, lens_tweak="regenerate")
        updated = _set_field(d, field, big_idea).model_copy(update={"brain": brain})
    else:
        updated = _set_field(d, field, _regenerate_spec_field(project_id, d, field))
    _emit_updated(d.id, DirectionChange.regenerate_field)
    return Command(goto=_route_after_field_change(field), update={"directions": [updated]})


def _recritique(project_id: str, directions: list, op: dict) -> Command:
    d = _by_id(directions, op["direction_id"])
    if d is None:
        return Command(goto=_GATE)
    critique = exploration.critique_one(project_id, d)
    updated = d.model_copy(update={"critique": critique, "critique_stale": False})
    _emit_updated(d.id, DirectionChange.recritique)
    return Command(goto=_DIVERGENCE, update={"directions": [updated]})


def _fork(project_id: str, directions: list, op: dict) -> Command:
    parent = _by_id(directions, op["direction_id"])
    if parent is None:
        return Command(goto=_GATE)
    lens_tweak = op.get("lens_tweak")
    big_idea, brain = exploration.ideate_one(project_id, parent.territory, lens_tweak=lens_tweak)
    art, copy = exploration.build_spec(project_id, parent.territory, big_idea)
    child_id = exploration.direction_id(project_id, f"{parent.id}:fork:{lens_tweak or ''}")
    child = Direction(
        id=child_id,
        territory=parent.territory,
        big_idea=big_idea,
        brain=brain,
        art_direction=art,
        copy=copy,
        sketches=[],
        parent_id=parent.id,
        lens_tweak=lens_tweak,
    )
    child = child.model_copy(update={"critique": exploration.critique_one(project_id, child)})
    child = exploration.attach_visuals(project_id, child)  # fresh sketches + moodboard
    get_stream_writer()(
        {"type": EventType.direction_created.value, "direction_id": child.id, "brain": brain}
    )
    return Command(goto=_DIVERGENCE, update={"directions": [child]})


def _merge(project_id: str, directions: list, op: dict) -> Command:
    parent_ids = op.get("direction_ids", [])
    field_choices = op.get("field_choices", {})
    parents = [_by_id(directions, pid) for pid in parent_ids]
    if len(parents) < 2 or any(p is None for p in parents):
        return Command(goto=_GATE)
    base = parents[0]
    merged_id = exploration.direction_id(project_id, "merge:" + ":".join(parent_ids))
    # Start from the first parent, then apply each GRANULAR field choice: every
    # editable field (dotted, e.g. copy.headline / art_direction.imagery_direction)
    # may be sourced from a different parent per `field_choices`. (moodboard is
    # regenerated fresh below per §10.9, so any moodboard choice is moot.)
    merged = base.model_copy(
        update={
            "id": merged_id,
            "merged_from": list(parent_ids),
            "parent_id": None,
            "status": "draft",
            "annotations": [],
            "sketches": [],
        }
    )
    for field in EDITABLE_FIELDS:
        chosen_id = field_choices.get(field)
        source = _by_id(directions, chosen_id) if chosen_id else None
        if source is not None:
            merged = _set_field(merged, field, _get_field(source, field))
    merged = merged.model_copy(
        update={"critique": exploration.critique_one(project_id, merged), "critique_stale": False}
    )
    merged = exploration.attach_visuals(project_id, merged)  # fresh batch; parents' sketches dropped
    updated_parents = [p.model_copy(update={"status": "merged_away"}) for p in parents]
    get_stream_writer()(
        {"type": EventType.direction_created.value, "direction_id": merged.id, "brain": merged.brain}
    )
    return Command(goto=_DIVERGENCE, update={"directions": [merged, *updated_parents]})


def _finalize(directions: list, op: dict) -> Command:
    promoted = [d for d in directions if d.status == "promoted"]
    if not promoted:
        # finalize requires at least one promoted direction — stay at the gate.
        return Command(goto=_GATE)
    refine = op.get("refine")
    do_refine = get_settings().refine_on_finalize if refine is None else bool(refine)
    return Command(goto="refine" if do_refine else "package")


# --------------------------------------------------------------------------- #
# visual regeneration ops (no critique/divergence effect — §10.9)             #
# --------------------------------------------------------------------------- #
def _regenerate_sketch(project_id: str, directions: list, op: dict) -> Command:
    from app.services import sketches as sketch_svc

    d = _by_id(directions, op["direction_id"])
    if d is None:
        return Command(goto=_GATE)
    index = op.get("index", 0)
    if not (0 <= index < len(d.sketches)):
        return Command(goto=_GATE)
    new_sketches = sketch_svc.regenerate_single(
        d.sketches, index, d.id, d.big_idea, d.territory.lens, project_id=project_id, prompt=op.get("prompt")
    )
    _emit_updated(d.id, DirectionChange.regenerate_sketch)
    return Command(goto=_GATE, update={"directions": [d.model_copy(update={"sketches": new_sketches})]})


def _regenerate_sketches(project_id: str, directions: list, op: dict) -> Command:
    from app.services import sketches as sketch_svc

    d = _by_id(directions, op["direction_id"])
    if d is None:
        return Command(goto=_GATE)
    new_sketches = sketch_svc.regenerate_batch(d.sketches, d.id, d.big_idea, d.territory.lens, project_id=project_id)
    _emit_updated(d.id, DirectionChange.regenerate_sketches)
    return Command(goto=_GATE, update={"directions": [d.model_copy(update={"sketches": new_sketches})]})


def _regenerate_moodboard_item(project_id: str, directions: list, op: dict) -> Command:
    from app.services import moodboard as moodboard_svc

    d = _by_id(directions, op["direction_id"])
    if d is None:
        return Command(goto=_GATE)
    index = op.get("index", 0)
    board = d.art_direction.moodboard
    if not (0 <= index < len(board)):
        return Command(goto=_GATE)
    new_board = moodboard_svc.regenerate_slot(
        board,
        index,
        d.id,
        d.art_direction.mood_descriptors,
        d.art_direction.imagery_direction,
        project_id=project_id,
        palette=d.art_direction.palette,
        kind=op.get("kind"),
        prompt=op.get("prompt"),
    )
    art = d.art_direction.model_copy(update={"moodboard": new_board})
    _emit_updated(d.id, DirectionChange.regenerate_moodboard_item)
    return Command(goto=_GATE, update={"directions": [d.model_copy(update={"art_direction": art})]})
