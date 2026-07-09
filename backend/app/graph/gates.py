"""Human gates: strategy approval (Gate 1) and the ideation gate.

``strategy_gate`` is a human-in-the-loop interrupt. It pauses the graph by
calling ``interrupt(...)`` as its FIRST statement (the node re-executes from the
top on resume, so NO side effects may precede the interrupt), surfaces the
current strategy for review, and routes on the human decision:

  * approve -> continue to ``verbal`` (optionally applying inline edits);
  * reject  -> back to ``strategize`` carrying the reviewer's notes.

``ideation_gate`` sits between ``seed`` and the explore fan-out. In internal /
conceptial modes it routes straight through. In manual mode it pauses so the
operator can take the ideation packet to an external creative LLM/agent, paste
the brainstormed ideas back (op ``submit`` — each idea is critiqued in-house and
the gate re-interrupts so the operator can iterate), and finally ``proceed`` —
the explore branches then build on the submitted ideas.
"""

from __future__ import annotations

from langgraph.types import Command, interrupt

from app.graph.exploration import route_to_territories
from app.models.artifacts import CostRecord
from app.models.events import EventType
from app.models.state import GraphState
from app.services.models import last_usage, reset_usage


def strategy_gate(state: GraphState) -> Command:
    strategy = state.get("strategy")
    decision = interrupt(
        {
            "gate": "strategy",
            "strategy": strategy.model_dump() if strategy else None,
        }
    )
    if decision.get("action") == "approve":
        edits = decision.get("edits") or {}
        update: dict = {"edited_by_human": bool(edits)}
        if edits and strategy is not None:
            # Re-validate the merged strategy so an invalid inline edit can never
            # enter state (provenance/validation-at-the-boundary, §02). The API
            # rejects bad edits with 422 first; this is defense-in-depth.
            update["strategy"] = type(strategy).model_validate(
                {**strategy.model_dump(), **edits}
            )
        return Command(goto="verbal", update=update)
    return Command(
        goto="strategize",
        update={"rejection_notes": decision.get("notes", "")},
    )


def ideation_gate(state: GraphState) -> Command:
    """Route to the explore fan-out — pausing first for external ideas in manual
    mode. Always returns a Command (the fan-out is a list of Sends), so this node
    needs no static edges."""
    mode = state.get("ideation_mode") or "internal"
    if mode != "manual":
        return Command(goto=route_to_territories(state))

    territories = state.get("territories") or []
    reviews = state.get("ideation_reviews") or []
    decision = interrupt(
        {
            "gate": "ideation",
            "territories": [t.model_dump() for t in territories],
            "reviews": [r.model_dump() for r in reviews],
        }
    )
    if decision.get("action") == "submit":
        # Parse the pasted external-tool output, critique each idea in-house,
        # and re-interrupt so the operator can iterate (or proceed).
        from langgraph.config import get_stream_writer

        from app.services.ideation import parse_external_ideas, review_ideas

        writer = get_stream_writer()
        project_id = state.get("project_id", "")
        ideas = parse_external_ideas(
            decision.get("ideas_text", ""), territories, project_id=project_id
        )
        reset_usage()
        writer({"type": EventType.agent_started.value, "agent": "idea_critique"})
        reviewed = review_ideas(project_id, ideas, strategy=state.get("strategy"))
        usage = last_usage()
        cost = CostRecord(
            agent="idea_critique",
            model="critic",
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
        )
        writer({"type": EventType.agent_completed.value, "agent": "idea_critique"})
        writer({"type": EventType.cost_recorded.value, **cost.model_dump()})
        return Command(
            goto="ideation_gate",
            update={"ideation_reviews": reviewed, "costs": [cost]},
        )
    # proceed — explore with whatever ideas were submitted (none = internal ideation)
    return Command(goto=route_to_territories(state))
