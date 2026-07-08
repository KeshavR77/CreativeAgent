"""Graph assembly (§9/§10, sub-plans 03–04).

Wires the full backend graph over ``GraphState``:

    START -> interrogate -> research -> strategize -> strategy_gate
             strategy_gate --(approve)--> verbal -> briefwrite -> seed
             strategy_gate --(reject)---> strategize      (re-runs, re-interrupts)
    seed --(Send per territory)--> explore_territory -> divergence -> curation_gate
             curation_gate --(promote/kill/annotate/edit/...)--> curation_gate (loop)
             curation_gate --(finalize)--> refine -> package -> END   (or package directly)

A ``Send`` fan-out explores K territories in parallel; ``divergence`` is the
fan-in. Provider nodes carry a ``RetryPolicy`` that retries ONLY transient
transport errors — a malformed model output (``AgentOutputError``) surfaces.
Must be compiled WITH a checkpointer and invoked with a ``thread_id``.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, Send

from app.config import get_settings
from app.graph.curation import curation_gate
from app.graph.exploration import divergence_node, explore_territory, package, refine
from app.graph.gates import strategy_gate
from app.graph.nodes import (
    briefwrite,
    interrogate,
    research,
    seed,
    strategize,
    verbal,
)
from app.models.state import GraphState
from app.services.models import AgentOutputError


def _transient(exc: Exception) -> bool:
    """Retry only transient transport errors; never a bad model output."""
    if isinstance(exc, AgentOutputError):
        return False
    return isinstance(exc, (ConnectionError, TimeoutError))


def _route_to_territories(state: GraphState) -> list[Send]:
    """Fan out one ``explore_territory`` branch per territory, capped at K. A real
    model may overshoot the requested territory count; without the cap each extra
    territory costs a full explore branch (chat + sketches + moodboard). A Send
    branch does NOT see accumulated state, so all context travels in the payload."""
    project_id = state["project_id"]
    strategy = state.get("strategy")
    creative_brief = state.get("creative_brief")
    verbal_identity = state.get("verbal_identity")
    k = max(2, get_settings().K)
    return [
        Send(
            "explore_territory",
            {
                "project_id": project_id,
                "territory": territory.model_dump(),
                "strategy": strategy.model_dump() if strategy is not None else None,
                "creative_brief": creative_brief.model_dump() if creative_brief is not None else None,
                "verbal_identity": verbal_identity.model_dump() if verbal_identity is not None else None,
            },
        )
        for territory in state.get("territories", [])[:k]
    ]


def build_graph(checkpointer):
    """Compile the full backend graph against ``checkpointer`` (durable interrupts)."""
    retry = RetryPolicy(max_attempts=3, retry_on=_transient)

    g = StateGraph(GraphState)
    # --- spine (sub-plan 03) ---
    g.add_node("interrogate", interrogate)
    g.add_node("research", research, retry_policy=retry)
    g.add_node("strategize", strategize, retry_policy=retry)
    g.add_node("strategy_gate", strategy_gate)
    g.add_node("verbal", verbal, retry_policy=retry)
    g.add_node("briefwrite", briefwrite, retry_policy=retry)
    g.add_node("seed", seed, retry_policy=retry)
    # --- fan-out + gate 2 (sub-plan 04) ---
    g.add_node("explore_territory", explore_territory)  # self-handles branch failure
    g.add_node("divergence", divergence_node)
    g.add_node("curation_gate", curation_gate)
    g.add_node("refine", refine)
    g.add_node("package", package)

    g.add_edge(START, "interrogate")
    g.add_edge("interrogate", "research")
    g.add_edge("research", "strategize")
    g.add_edge("strategize", "strategy_gate")
    # strategy_gate routes dynamically via Command(goto=...).
    g.add_edge("verbal", "briefwrite")
    g.add_edge("briefwrite", "seed")
    g.add_conditional_edges("seed", _route_to_territories, ["explore_territory"])
    g.add_edge("explore_territory", "divergence")
    g.add_edge("divergence", "curation_gate")
    # curation_gate routes dynamically (self-loop for ops, refine/package on finalize).
    g.add_edge("refine", "package")
    g.add_edge("package", END)

    return g.compile(checkpointer=checkpointer)
