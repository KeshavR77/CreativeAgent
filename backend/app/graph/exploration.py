"""Fan-out exploration, critic, divergence, refine & package (Stage 04, §10.7/§10.8/§11).

Each seeded territory is explored in parallel (idea -> spec -> critic) via `Send`;
the branches fan in at `divergence_node`, which scores how distinct the surviving
directions are. `refine`/`package` turn promoted directions into ConceptPackages.

Inner helpers (`ideate_one`, `build_spec`, `critique_one`) are reused by the
curation ops (fork/merge/regenerate/recritique). Sketches/moodboards are stubbed
empty here and land in sub-plan 05.
"""

from __future__ import annotations

import hashlib

from langchain_core.messages import SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.artifacts import (
    ArtDirectionSpec,
    ConceptPackage,
    CopyDeck,
    CostRecord,
    CritiqueScore,
    Direction,
    PaletteColor,
    Territory,
    TypeChoice,
)
from app.models.events import EventType
from app.models.state import GraphState
from app.services.conceptial import ConceptialUnavailable
from app.services.conceptial import generate as conceptial_generate
from app.services.divergence import divergence_report
from app.services.models import generate_structured, get_chat_model, last_usage
from app.services.prompts import render_prompt


# --------------------------------------------------------------------------- #
# node-output schemas (model produces these; nodes assemble domain objects)   #
# --------------------------------------------------------------------------- #
class IdeaResult(BaseModel):
    big_idea: str


class SpecResult(BaseModel):
    imagery_direction: str
    mood_descriptors: list[str] = Field(default_factory=list)
    layout_notes: str = ""
    palette: list[PaletteColor] = Field(default_factory=list)
    typography: list[TypeChoice] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def direction_id(project_id: str, discriminator: str) -> str:
    digest = hashlib.md5(f"{project_id}:{discriminator}".encode("utf-8")).hexdigest()
    return f"dir-{digest[:10]}"


def _model_name(model) -> str:
    return getattr(model, "_llm_type", "unknown")


def compute_verdict(score: CritiqueScore) -> str:
    """Verdict is computed in code (§10.8), never taken from the model."""
    avg = (
        score.distinctiveness
        + score.strategic_fit
        + score.memorability
        + score.audience_resonance
        + score.feasibility
    ) / 5.0
    if avg >= 4.0:
        return "ship"
    if avg >= 2.5:
        return "revise"
    return "kill"


# --------------------------------------------------------------------------- #
# reusable inner steps                                                         #
# --------------------------------------------------------------------------- #
def ideate_one(project_id: str, territory: Territory, *, lens_tweak: str | None = None) -> tuple[str, str]:
    """Return (big_idea, brain). Conceptial when configured, else claude_high_temp
    / mock — ``brain`` is recorded truthfully (never "conceptial" for a fallback)."""
    settings = get_settings()
    lens = territory.lens if not lens_tweak else f"{territory.lens} — {lens_tweak}"
    if settings.conceptial_mode == "real":
        try:
            ideas = conceptial_generate(
                creative_brief=f"{territory.label} — {lens}", territory=territory, n_ideas=1
            )
            if ideas:
                return ideas[0]["big_idea"], "conceptial"
        except ConceptialUnavailable:
            pass
    # fallback: the ideator fallback runs the generator hot (temp 1.0).
    model = get_chat_model("ideator", project_id=project_id, temperature=1.0, seed_extra=territory.label)
    prompt = [SystemMessage(content=render_prompt("idea", territory=territory.label, lens=lens))]
    big_idea = generate_structured(model, prompt, IdeaResult).big_idea
    brain = "claude_high_temp" if settings.claude_mode == "real" else "mock"
    return big_idea, brain


def build_spec(project_id: str, territory: Territory, big_idea: str) -> tuple[ArtDirectionSpec, CopyDeck]:
    """Produce the ArtDirectionSpec (moodboard stubbed empty) + CopyDeck."""
    model = get_chat_model("spec", project_id=project_id, temperature=0.7, seed_extra=territory.label)
    prompt = [SystemMessage(content=render_prompt("spec", territory=territory.label, big_idea=big_idea))]
    spec = generate_structured(model, prompt, SpecResult)
    art = ArtDirectionSpec(
        imagery_direction=spec.imagery_direction,
        mood_descriptors=spec.mood_descriptors,
        layout_notes=spec.layout_notes,
        palette=spec.palette,
        typography=spec.typography,
        moodboard=[],  # sketches/moodboard land in sub-plan 05
    )
    copy = generate_structured(model, prompt, CopyDeck)
    return art, copy


def critique_one(project_id: str, direction: Direction) -> CritiqueScore:
    """Independent critique (fresh context, distinct model role). Verdict is
    computed in code; the real critic model is recorded."""
    model = get_chat_model("critic", project_id=project_id, temperature=0.3, seed_extra=direction.id)
    prompt = [
        SystemMessage(
            content=render_prompt("critic", big_idea=direction.big_idea, headline=direction.copy.headline)
        )
    ]
    raw = generate_structured(model, prompt, CritiqueScore)
    return raw.model_copy(update={"verdict": compute_verdict(raw), "critic_model": _model_name(model)})


# --------------------------------------------------------------------------- #
# graph nodes                                                                  #
# --------------------------------------------------------------------------- #
def attach_visuals(project_id: str, direction: Direction) -> Direction:
    """Generate concept sketches + a hybrid moodboard for a direction (§10.7 steps
    3-4). Reused by fork/merge so every direction carries visuals; keyless these
    resolve to placeholders. Every image is provenance-complete by construction."""
    from app.services import moodboard as moodboard_svc
    from app.services import sketches as sketch_svc

    sk = sketch_svc.generate(direction.id, direction.big_idea, direction.territory.lens, project_id=project_id)
    mb = moodboard_svc.build(
        direction.id,
        direction.art_direction.mood_descriptors,
        direction.art_direction.imagery_direction,
        project_id=project_id,
        palette=direction.art_direction.palette,
    )
    art = direction.art_direction.model_copy(update={"moodboard": mb})
    return direction.model_copy(update={"sketches": sk, "art_direction": art})


def _visual_costs(direction: Direction, base: CostRecord) -> list[CostRecord]:
    model = get_settings().IMAGE_GEN_MODEL
    return [
        base,
        CostRecord(agent="sketches", model=model, output_tokens=len(direction.sketches)),
        CostRecord(agent="moodboard", model=model, output_tokens=len(direction.art_direction.moodboard)),
    ]


def explore_territory(state: GraphState) -> dict:
    """One fan-out branch: idea -> spec -> critic. Receives its territory + context
    via the Send payload (a Send branch does NOT see accumulated state)."""
    writer = get_stream_writer()
    project_id = state["project_id"]
    territory = Territory.model_validate(state["territory"])
    label = territory.label
    try:
        writer({"type": EventType.agent_started.value, "agent": "explore", "territory": label})
        big_idea, brain = ideate_one(project_id, territory)
        art, copy = build_spec(project_id, territory, big_idea)
        direction = Direction(
            id=direction_id(project_id, label),
            territory=territory,
            big_idea=big_idea,
            brain=brain,
            art_direction=art,
            copy=copy,
            sketches=[],
        )
        critique = critique_one(project_id, direction)
        direction = direction.model_copy(update={"critique": critique})
        direction = attach_visuals(project_id, direction)  # sketches + hybrid moodboard (§10.7 steps 3-4)
        writer({"type": EventType.direction_created.value, "direction_id": direction.id, "brain": brain})
        # real chat-token cost for this branch's ideate/spec/copy/critique calls
        # (accumulated in the per-branch context; 0 for the mock).
        usage = last_usage()
        explore_cost = CostRecord(
            agent="explore",
            model=brain,
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
        )
        return {"directions": [direction], "costs": _visual_costs(direction, explore_cost)}
    except Exception as exc:  # noqa: BLE001 - a failed territory must not kill the run
        writer(
            {"type": EventType.agent_failed.value, "agent": "explore", "territory": label, "error": str(exc)}
        )
        return {"failed_territories": [label]}


def divergence_node(state: GraphState) -> dict:
    """Fan-in: score how distinct the active directions are. Writes an overall
    {min, mean, warning} and a per-direction divergence_score. Text-only (§11)."""
    writer = get_stream_writer()
    directions = state.get("directions", [])
    active = [d for d in directions if d.status not in ("killed", "merged_away")]
    if len(active) < 2:
        # Divergence is undefined for <2 concepts; don't crash the run.
        result = {"min": None, "mean": None, "warning": False}
        writer({"type": EventType.divergence_computed.value, **result})
        return {"divergence": result}
    report = divergence_report(directions)
    scores = report["scores"]
    updated = [
        d.model_copy(update={"divergence_score": scores[d.id]})
        for d in directions
        if d.id in scores
    ]
    result = {"min": report["min"], "mean": report["mean"], "warning": report["warning"]}
    writer({"type": EventType.divergence_computed.value, **result})
    return {"divergence": result, "directions": updated}


def refine(state: GraphState) -> dict:
    """Light polish pass over promoted directions before packaging (§10.10).

    On mocks this is a no-op beyond an observability event; real refinement lands
    with real providers (sub-plan 07)."""
    writer = get_stream_writer()
    writer({"type": EventType.agent_started.value, "agent": "refine"})
    writer({"type": EventType.agent_completed.value, "agent": "refine"})
    return {}


def package(state: GraphState) -> dict:
    """Build a ConceptPackage per promoted direction (§10.10) -> END."""
    writer = get_stream_writer()
    strategy = state.get("strategy")
    verbal = state.get("verbal_identity")
    names = list(verbal.names) if verbal is not None else []
    packages = []
    for direction in state.get("directions", []):
        if direction.status != "promoted":
            continue
        rationale = direction.big_idea
        if strategy is not None:
            rationale = f"{direction.big_idea} — {strategy.key_message}"
        packages.append(
            ConceptPackage(
                direction_id=direction.id,
                territory_label=direction.territory.label,
                strategy=strategy,
                big_idea=direction.big_idea,
                names=names,
                sketches=direction.sketches,
                art_direction=direction.art_direction,
                copy=direction.copy,
                rationale=rationale,
            )
        )
    writer({"type": EventType.artifact_written.value, "artifact": "packages"})
    return {"packages": packages}
