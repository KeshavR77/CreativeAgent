"""Graph assembly: the spine, the gates, and the ideation modes.

Wires the full backend graph over ``GraphState``:

    START -> interrogate -> research -> strategize -> strategy_gate
             strategy_gate --(approve)--> verbal -> briefwrite -> seed
             strategy_gate --(reject)---> strategize      (re-runs, re-interrupts)
    seed -> ideation_gate
             ideation_gate --(internal/auto)--> Send per territory (no pause)
             ideation_gate --(manual: submit)------> ideation_gate (critique loop)
             ideation_gate --(manual: proceed)-----> Send per territory
    explore_territory -> divergence -> curation_gate
             curation_gate --(promote/kill/annotate/edit/...)--> curation_gate (loop)
             curation_gate --(finalize)--> refine -> package -> END   (or package directly)

A ``Send`` fan-out explores K territories in parallel; ``divergence`` is the
fan-in. Provider nodes carry a ``RetryPolicy`` that retries ONLY transient
transport errors — a malformed model output (``AgentOutputError``) surfaces.
Must be compiled WITH a checkpointer and invoked with a ``thread_id``.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.graph.curation import curation_gate
from app.graph.exploration import divergence_node, explore_territory, package, refine
from app.graph.gates import ideation_gate, strategy_gate
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


def build_graph(checkpointer):
    """Compile the full backend graph against ``checkpointer`` (durable interrupts)."""
    retry = RetryPolicy(max_attempts=3, retry_on=_transient)

    g = StateGraph(GraphState)
    # --- spine ---
    g.add_node("interrogate", interrogate)
    g.add_node("research", research, retry_policy=retry)
    g.add_node("strategize", strategize, retry_policy=retry)
    g.add_node("strategy_gate", strategy_gate)
    g.add_node("verbal", verbal, retry_policy=retry)
    g.add_node("briefwrite", briefwrite, retry_policy=retry)
    g.add_node("seed", seed, retry_policy=retry)
    # --- ideation gate + fan-out + gate 2 ---
    # ideation_gate routes dynamically: straight to the Send fan-out (internal /
    # auto), or interrupt-and-loop for externally-brainstormed ideas (manual).
    g.add_node("ideation_gate", ideation_gate)
    # explore_territory self-handles branch failure AND retries transient GLM
    # errors internally; the node-level retry is a second belt for transport blips.
    g.add_node("explore_territory", explore_territory, retry_policy=retry)
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
    g.add_edge("seed", "ideation_gate")
    # ideation_gate routes dynamically (Sends to explore_territory, or self-loop).
    g.add_edge("explore_territory", "divergence")
    g.add_edge("divergence", "curation_gate")
    # curation_gate routes dynamically (self-loop for ops, refine/package on finalize).
    g.add_edge("refine", "package")
    g.add_edge("package", END)

    return g.compile(checkpointer=checkpointer)
