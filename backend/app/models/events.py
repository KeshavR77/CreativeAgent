"""Run-state machine + event vocabulary.

`RunState` is the durable lifecycle state cached in the registry. `NODE_RUN_STATE`
/ `GATE_RUN_STATE` map graph nodes to the state reported while they run. Event
type constants (with documented payload shapes) are the wire vocabulary the
RunManager appends to the event log and the SSE stream replays.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, TypedDict


class RunState(str, Enum):
    """Durable lifecycle state for a run (intake … done/cancelled/error)."""

    intake = "intake"
    interrogating = "interrogating"
    researching = "researching"
    strategizing = "strategizing"
    awaiting_strategy_approval = "awaiting_strategy_approval"  # gate 1
    naming = "naming"          # verbal node
    briefing = "briefing"      # briefwrite node
    seeding = "seeding"        # seed node
    awaiting_ideation = "awaiting_ideation"  # ideation gate (manual mode only)
    exploring = "exploring"    # fan-out branches
    diverging = "diverging"    # divergence fan-in
    awaiting_curation = "awaiting_curation"  # gate 2
    refining = "refining"
    packaging = "packaging"
    done = "done"
    cancelled = "cancelled"
    error = "error"


# node name -> state reported while that node executes.
NODE_RUN_STATE: dict[str, RunState] = {
    "interrogate": RunState.interrogating,
    "research": RunState.researching,
    "strategize": RunState.strategizing,
    "verbal": RunState.naming,
    "briefwrite": RunState.briefing,
    "seed": RunState.seeding,
    "explore_territory": RunState.exploring,
    "divergence": RunState.diverging,
    "refine": RunState.refining,
    "package": RunState.packaging,
}

# gate node -> the awaiting_* state entered when it interrupts.
GATE_RUN_STATE: dict[str, RunState] = {
    "strategy_gate": RunState.awaiting_strategy_approval,
    "ideation_gate": RunState.awaiting_ideation,
    "curation_gate": RunState.awaiting_curation,
}

# States a crashed process must NOT auto-resume: waiting on a human, terminal,
# or never-started. Everything else (mid-run nodes, `error`) is resumable.
NON_RESUMABLE_STATES: frozenset[RunState] = frozenset(
    {
        RunState.awaiting_strategy_approval,
        RunState.awaiting_ideation,
        RunState.awaiting_curation,
        RunState.done,
        RunState.cancelled,
        RunState.intake,
    }
)


class EventType(str, Enum):
    """Durable event-log / SSE event vocabulary (run_created … run_cancelled)."""

    run_created = "run_created"
    run_state_changed = "run_state_changed"
    agent_started = "agent_started"
    agent_completed = "agent_completed"
    agent_failed = "agent_failed"
    agent_token = "agent_token"
    artifact_written = "artifact_written"
    direction_created = "direction_created"
    direction_updated = "direction_updated"
    divergence_computed = "divergence_computed"
    gate_reached = "gate_reached"
    gate_resolved = "gate_resolved"
    cost_recorded = "cost_recorded"
    run_cancelled = "run_cancelled"


class DirectionChange(str, Enum):
    """The `change` discriminator on a `direction_updated` event."""

    edit = "edit"
    regenerate_field = "regenerate_field"
    regenerate_sketch = "regenerate_sketch"
    regenerate_sketches = "regenerate_sketches"
    regenerate_moodboard_item = "regenerate_moodboard_item"
    recritique = "recritique"


# --------------------------------------------------------------------------- #
# payload shapes (documentation; the graph nodes fill them)                    #
# total=False keeps them permissive — the SSE layer serializes plain dicts.    #
# --------------------------------------------------------------------------- #
class RunCreatedPayload(TypedDict, total=False):
    project_id: str
    brief_excerpt: str


class RunStateChangedPayload(TypedDict, total=False):
    from_state: str
    to_state: str


class GatePayload(TypedDict, total=False):
    gate: str  # "strategy" | "curation"
    payload: dict


class DirectionCreatedPayload(TypedDict, total=False):
    direction_id: str
    brain: str  # truthful ideator: external_ideator | claude_high_temp | mock


class DirectionUpdatedPayload(TypedDict, total=False):
    direction_id: str
    change: str  # one of DirectionChange


class DivergenceComputedPayload(TypedDict, total=False):
    min: float
    mean: float
    warning: bool


class AgentEventPayload(TypedDict, total=False):
    agent: str
    error: Optional[str]
