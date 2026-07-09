"""The six spine nodes of the Stage-03 graph (§10, sub-plan 03).

Each node is a SYNC function ``def node(state: GraphState) -> dict`` returning a
partial state delta (``GraphState`` is ``total=False``). Provider nodes emit
observability events through LangGraph's ``get_stream_writer()`` (the RunManager
turns those custom-stream dicts into durable events) and record exactly ONE new
``CostRecord`` per call — ``costs`` accumulates with ``operator.add``, so
re-emitting the whole list would double-count.

Keyless-first: models resolve to the deterministic mock under an empty
environment, so the spine runs end-to-end with ZERO provider keys.
"""

from __future__ import annotations

from pydantic import BaseModel

from langgraph.config import get_stream_writer
from langgraph.types import interrupt

from app.config import get_settings
from app.models.artifacts import (
    CostRecord,
    CreativeBrief,
    ResearchDossier,
    Strategy,
    Territory,
    VerbalIdentity,
)
from app.models.events import EventType
from app.models.state import GraphState
from app.services.mock_chat import _phrase, register_builder
from app.services.models import generate_structured, get_chat_model, last_usage
from app.services.prompts import render_prompt
from app.services.search import search


class SeedResult(BaseModel):
    """Structured-output container: the seed node yields a list of territories."""

    territories: list[Territory]


def _build_seed_result(seed: str) -> SeedResult:
    """Mock builder: emit exactly ``K`` distinct territories.

    The generic list builder only makes two, which would under-fan-out and make a
    single branch failure collapse divergence to one direction. Real models
    produce their own territories from the prompt (this only shapes the mock).
    """
    k = max(2, get_settings().K)
    territories = [
        Territory(
            label=_phrase(f"{seed}:label:{i}", 3).title(),
            lens=_phrase(f"{seed}:lens:{i}", 5),
            description=_phrase(f"{seed}:desc:{i}", 8),
        )
        for i in range(k)
    ]
    return SeedResult(territories=territories)


register_builder(SeedResult, _build_seed_result)


def _writer():
    return get_stream_writer()


def _started(write, agent: str) -> None:
    write({"type": EventType.agent_started.value, "agent": agent})


def _completed(write, agent: str, artifact: str) -> None:
    write({"type": EventType.artifact_written.value, "artifact": artifact})
    write({"type": EventType.agent_completed.value, "agent": agent})


def _cost(agent: str, model, write=None) -> CostRecord:
    """Cost for the most recent structured call (real token counts when running a
    real model; 0 for the mock). When ``write`` is given, also emits the
    ``cost_recorded`` event so the Studio cost footer ticks live."""
    usage = last_usage()
    rec = CostRecord(
        agent=agent,
        model=model._llm_type,
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
    )
    if write is not None:
        write({"type": EventType.cost_recorded.value, **rec.model_dump()})
    return rec


def interrogate(state: GraphState) -> dict:
    """Optional human clarification gate.

    When ``ask_clarifying_questions`` is on, this node pauses FIRST (no side
    effects before ``interrupt`` — the node re-executes on resume) and records
    the answers. Off by default: it is a no-op pass-through.
    """
    settings = get_settings()
    if settings.ask_clarifying_questions:
        answers = interrupt(
            {
                "gate": "clarify",
                "questions": ["What does success look like?", "Who is the audience?"],
            }
        )
        return {"clarifying_answers": list(answers.get("answers", []))}
    write = _writer()
    _started(write, "interrogate")
    write({"type": EventType.agent_completed.value, "agent": "interrogate"})
    return {}


def research(state: GraphState) -> dict:
    settings = get_settings()
    write = _writer()
    _started(write, "research")
    brief = state["brief"]
    sources = search(brief.brief, k=settings.K)
    model = get_chat_model("research", project_id=state["project_id"])
    prompt = render_prompt(
        "research", brief=brief.brief, audience=brief.audience, sources=sources
    )
    dossier: ResearchDossier = generate_structured(model, prompt, ResearchDossier)
    dossier = dossier.model_copy(update={"sources": sources})
    _completed(write, "research", "research")
    return {"research": dossier, "costs": [_cost("research", model, write)]}


def strategize(state: GraphState) -> dict:
    write = _writer()
    _started(write, "strategize")
    brief = state["brief"]
    dossier = state.get("research")
    model = get_chat_model("strategize", project_id=state["project_id"])
    prompt = render_prompt(
        "strategize",
        brief=brief.brief,
        clarifying_answers="; ".join(state.get("clarifying_answers") or []),
        research=(dossier.summary if dossier else ""),
        rejection_notes=state.get("rejection_notes", ""),
    )
    strategy: Strategy = generate_structured(model, prompt, Strategy)
    _completed(write, "strategize", "strategy")
    return {"strategy": strategy, "costs": [_cost("strategize", model, write)]}


def verbal(state: GraphState) -> dict:
    write = _writer()
    _started(write, "verbal")
    brief = state["brief"]
    strategy = state.get("strategy")
    model = get_chat_model("verbal", project_id=state["project_id"])
    prompt = render_prompt(
        "verbal",
        strategy=(strategy.model_dump() if strategy else {}),
        audience=brief.audience,
    )
    identity: VerbalIdentity = generate_structured(model, prompt, VerbalIdentity)
    _completed(write, "verbal", "verbal_identity")
    return {"verbal_identity": identity, "costs": [_cost("verbal", model, write)]}


def briefwrite(state: GraphState) -> dict:
    write = _writer()
    _started(write, "briefwrite")
    brief = state["brief"]
    strategy = state.get("strategy")
    model = get_chat_model("briefwrite", project_id=state["project_id"])
    prompt = render_prompt(
        "briefwrite",
        strategy=(strategy.model_dump() if strategy else {}),
        audience=brief.audience,
    )
    creative_brief: CreativeBrief = generate_structured(model, prompt, CreativeBrief)
    _completed(write, "briefwrite", "creative_brief")
    return {"creative_brief": creative_brief, "costs": [_cost("briefwrite", model, write)]}


def seed(state: GraphState) -> dict:
    write = _writer()
    _started(write, "seed")
    strategy = state.get("strategy")
    creative_brief = state.get("creative_brief")
    model = get_chat_model("seed", project_id=state["project_id"])
    prompt = render_prompt(
        "seed",
        strategy=(strategy.model_dump() if strategy else {}),
        creative_brief=(creative_brief.model_dump() if creative_brief else {}),
    )
    result: SeedResult = generate_structured(model, prompt, SeedResult)
    # Cap at K: a real model may return more territories than requested. The
    # fan-out explores only K, so storing more leaves orphan skeleton lanes in the
    # Studio that never fill. Keep the projection consistent with what runs.
    k = max(2, get_settings().K)
    territories = result.territories[:k]
    _completed(write, "seed", "territories")
    return {"territories": territories, "costs": [_cost("seed", model, write)]}
