"""Gate 1 — strategy approval (§9, sub-plan 03).

``strategy_gate`` is a human-in-the-loop interrupt. It pauses the graph by
calling ``interrupt(...)`` as its FIRST statement (the node re-executes from the
top on resume, so NO side effects may precede the interrupt), surfaces the
current strategy for review, and routes on the human decision:

  * approve -> continue to ``verbal`` (optionally applying inline edits);
  * reject  -> back to ``strategize`` carrying the reviewer's notes.
"""

from __future__ import annotations

from langgraph.types import Command, interrupt

from app.models.state import GraphState


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
