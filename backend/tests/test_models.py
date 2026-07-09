"""Domain-model contract tests (Stage 02, §6.1/§6.3/§16).

These lock the artifact schemas, the events/run-state vocabulary, and the view
shapes. Field names are contract: later stages import these models rather than
restating them. Provenance and other invariants are validated at the *model
boundary* — a violating instance must be unconstructible, not merely flagged.
"""

from __future__ import annotations

import operator

import pytest
from pydantic import ValidationError

from app.models.artifacts import (
    DIVERGENCE_FIELDS,
    EDITABLE_FIELDS,
    Annotation,
    ArtDirectionSpec,
    AudienceNote,
    Brief,
    CompetitorNote,
    ConceptPackage,
    CopyDeck,
    CostRecord,
    CreativeBrief,
    CritiqueScore,
    Direction,
    ImageRef,
    PaletteColor,
    ResearchDossier,
    SourceRef,
    Strategy,
    Territory,
    TypeChoice,
    VerbalIdentity,
)
from app.models.events import (
    GATE_RUN_STATE,
    NODE_RUN_STATE,
    NON_RESUMABLE_STATES,
    DirectionChange,
    EventType,
    RunState,
)
from app.models.views import EventOut, ProjectSummary, ProjectView


# --------------------------------------------------------------------------- #
# builders                                                                     #
# --------------------------------------------------------------------------- #
def gen_img(**kw) -> ImageRef:
    base = dict(
        kind="generated",
        url="/data/generated/p/d/x.png",
        provider="generated",
        license="AI-generated",
        gen_model="mock-diffusion",
        gen_prompt="a rough marker sketch of a running shoe",
    )
    base.update(kw)
    return ImageRef(**base)


def src_img(**kw) -> ImageRef:
    base = dict(
        kind="sourced",
        url="https://example.com/img/0001.jpg",
        provider="mock",
        license="CC0",
        source_url="https://example.com/img/0001",
        attribution="Jane Doe",
    )
    base.update(kw)
    return ImageRef(**base)


def ph_img(**kw) -> ImageRef:
    base = dict(
        kind="placeholder",
        url="/data/generated/p/d/ph.png",
        provider="placeholder",
        license="none",
        caption="sketch generation unavailable",
    )
    base.update(kw)
    return ImageRef(**base)


def art_dir(**kw) -> ArtDirectionSpec:
    base = dict(imagery_direction="grounded, earthy, honest product photography")
    base.update(kw)
    return ArtDirectionSpec(**base)


def direction(**kw) -> Direction:
    base = dict(
        id="dir_1",
        territory=Territory(label="Radical Transparency", lens="proof over promises"),
        big_idea="Show the seams: every material traced on the shoe itself.",
        brain="mock",
        art_direction=art_dir(),
        copy=CopyDeck(headline="Nothing to hide."),
        sketches=[gen_img(), gen_img()],
    )
    base.update(kw)
    return Direction(**base)


CASE_50 = " ".join(f"reason{i}" for i in range(50))
CASE_49 = " ".join(f"reason{i}" for i in range(49))


def critique(**kw) -> CritiqueScore:
    base = dict(
        distinctiveness=4,
        strategic_fit=5,
        memorability=3,
        audience_resonance=4,
        feasibility=3,
        case_against=CASE_50,
        verdict="revise",
        critic_model="mock-critic",
    )
    base.update(kw)
    return CritiqueScore(**base)


# --------------------------------------------------------------------------- #
# Brief                                                                        #
# --------------------------------------------------------------------------- #
def test_brief_happy_matches_fixture_shape() -> None:
    b = Brief(
        brief="Launch a sustainable sneaker brand for runners sick of greenwashing.",
        brand_name="",
        constraints=[],
        audience="runners frustrated by greenwashing",
    )
    assert b.brand_name == ""
    assert b.constraints == []


def test_brief_requires_nonempty_text() -> None:
    with pytest.raises(ValidationError):
        Brief(brief="")


# --------------------------------------------------------------------------- #
# research / strategy / verbal / creative-brief / territory / copy / cost      #
# (happy-path construction locks the field names)                              #
# --------------------------------------------------------------------------- #
def test_research_and_strategy_field_names() -> None:
    dossier = ResearchDossier(
        sources=[SourceRef(title="t", url="https://x", snippet="s", query="q")],
        competitors=[CompetitorNote(name="Allbirds", note="eco leader")],
        audience_notes=[AudienceNote(insight="distrusts vague eco claims")],
        summary="market distrusts greenwashing",
    )
    assert dossier.sources[0].title == "t"
    strat = Strategy(
        positioning="the anti-greenwashing running shoe",
        key_message="proof, not promises",
        pillars=["traceability", "durability"],
        rationale="because runners are skeptical",
    )
    assert strat.pillars == ["traceability", "durability"]


def test_verbal_creativebrief_territory_copy_cost() -> None:
    vi = VerbalIdentity(names=["Tread", "Proof"], tagline="Run honest.", tone="plain")
    assert vi.screened is False
    cb = CreativeBrief(
        objective="win skeptical runners",
        audience="runners",
        key_message="proof not promises",
    )
    assert cb.mandatories == []
    terr = Territory(label="Radical Transparency", lens="proof over promises")
    assert terr.lens == "proof over promises"
    tc = TypeChoice(role="heading", family="Inter")
    assert tc.role == "heading"
    cd = CopyDeck(headline="Nothing to hide.", cta="See the proof")
    assert cd.headline == "Nothing to hide."
    cost = CostRecord(agent="strategize", model="mock", input_tokens=10, output_tokens=20)
    assert cost.output_tokens == 20


def test_annotation_field_names() -> None:
    a = Annotation(text="push the headline harder", author="cd")
    assert a.author == "cd"


# --------------------------------------------------------------------------- #
# PaletteColor — hex validation (#RRGGBB)                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("hexval", ["#FFFFFF", "#ffffff", "#0a0A0a", "#123456"])
def test_palette_hex_valid(hexval: str) -> None:
    assert PaletteColor(name="c", hex=hexval).hex == hexval


@pytest.mark.parametrize("hexval", ["#FFF", "FFFFFF", "#GGGGGG", "#12345", "#1234567", ""])
def test_palette_hex_invalid(hexval: str) -> None:
    with pytest.raises(ValidationError):
        PaletteColor(name="c", hex=hexval)


# --------------------------------------------------------------------------- #
# ImageRef — per-kind provenance is unconstructible when violated              #
# --------------------------------------------------------------------------- #
def test_imageref_generated_happy() -> None:
    img = gen_img()
    assert img.kind == "generated"


@pytest.mark.parametrize("drop", ["gen_model", "gen_prompt"])
def test_imageref_generated_requires_gen_fields(drop: str) -> None:
    with pytest.raises(ValidationError):
        gen_img(**{drop: None})


def test_imageref_sourced_happy() -> None:
    assert src_img().kind == "sourced"


@pytest.mark.parametrize("drop", ["source_url", "attribution"])
def test_imageref_sourced_requires_source_fields(drop: str) -> None:
    with pytest.raises(ValidationError):
        src_img(**{drop: None})


def test_imageref_placeholder_happy() -> None:
    assert ph_img().kind == "placeholder"


@pytest.mark.parametrize("field", ["provider", "license"])
def test_imageref_all_kinds_require_provider_and_license(field: str) -> None:
    # provider + license are mandatory for EVERY kind.
    with pytest.raises(ValidationError):
        gen_img(**{field: ""})
    with pytest.raises(ValidationError):
        ph_img(**{field: ""})


def test_imageref_url_never_base64() -> None:
    with pytest.raises(ValidationError):
        gen_img(url="data:image/png;base64,AAAABBBBCCCC")


# --------------------------------------------------------------------------- #
# ArtDirectionSpec — moodboard 4–8 when populated, empty allowed (04 stub)     #
# --------------------------------------------------------------------------- #
def test_moodboard_empty_allowed() -> None:
    # Sub-plan 04 constructs the spec with an empty moodboard (filled in 05).
    assert art_dir().moodboard == []


# The model guards only the floor of 4; the exact count (targeting MOODBOARD_SIZE,
# default 9) is enforced by the moodboard service (sub-plan 05).
@pytest.mark.parametrize("n", [4, 6, 8, 9, 12])
def test_moodboard_valid_sizes(n: int) -> None:
    spec = art_dir(moodboard=[gen_img() for _ in range(n)])
    assert len(spec.moodboard) == n


@pytest.mark.parametrize("n", [1, 3])
def test_moodboard_below_floor_invalid(n: int) -> None:
    with pytest.raises(ValidationError):
        art_dir(moodboard=[gen_img() for _ in range(n)])


# --------------------------------------------------------------------------- #
# CritiqueScore — rubric v1, case_against >= 50 words, verdict literal          #
# --------------------------------------------------------------------------- #
def test_critique_happy() -> None:
    assert critique().verdict == "revise"


def test_critique_case_against_too_short() -> None:
    with pytest.raises(ValidationError):
        critique(case_against=CASE_49)


@pytest.mark.parametrize("score", [0, 6, -1, 10])
def test_critique_score_out_of_range(score: int) -> None:
    with pytest.raises(ValidationError):
        critique(distinctiveness=score)


def test_critique_bad_verdict() -> None:
    with pytest.raises(ValidationError):
        critique(verdict="ship-it-now")


# --------------------------------------------------------------------------- #
# VerbalIdentity — screened is a hard-coded False (no trademark screening)     #
# --------------------------------------------------------------------------- #
def test_verbal_identity_screened_must_be_false() -> None:
    with pytest.raises(ValidationError):
        VerbalIdentity(names=["X"], screened=True)


# --------------------------------------------------------------------------- #
# Direction.sketches — never sourced (generated + placeholder fallback ok)     #
# --------------------------------------------------------------------------- #
def test_direction_sketches_generated_ok() -> None:
    d = direction()
    assert all(s.kind == "generated" for s in d.sketches)
    assert d.critique_stale is False
    assert d.status == "draft"


def test_direction_sketches_placeholder_ok() -> None:
    # Under zero keys image-gen is disabled -> placeholder fallback (sub-plan 05).
    d = direction(sketches=[ph_img(), ph_img()])
    assert all(s.kind == "placeholder" for s in d.sketches)


def test_direction_sketches_reject_sourced() -> None:
    with pytest.raises(ValidationError):
        direction(sketches=[gen_img(), src_img()])


def test_direction_optional_lineage_and_critique() -> None:
    d = direction(
        critique=critique(),
        critique_stale=True,
        divergence_score=0.42,
        status="promoted",
        parent_id="dir_0",
        merged_from=["dir_a", "dir_b"],
        annotations=[Annotation(text="tighten")],
    )
    assert d.critique.verdict == "revise"
    assert d.merged_from == ["dir_a", "dir_b"]


# --------------------------------------------------------------------------- #
# ConceptPackage                                                               #
# --------------------------------------------------------------------------- #
def package(**kw) -> ConceptPackage:
    base = dict(
        direction_id="dir_1",
        territory_label="Radical Transparency",
        strategy=Strategy(positioning="p", key_message="k"),
        big_idea="Show the seams.",
        names=["Tread"],
        sketches=[gen_img()],
        art_direction=art_dir(),
        copy=CopyDeck(headline="Nothing to hide."),
        rationale="It converts skeptics with proof.",
    )
    base.update(kw)
    return ConceptPackage(**base)


def test_concept_package_happy() -> None:
    assert package().direction_id == "dir_1"


def test_concept_package_sketches_reject_sourced() -> None:
    with pytest.raises(ValidationError):
        package(sketches=[src_img()])


# --------------------------------------------------------------------------- #
# Editable-fields / divergence-fields constants                               #
# --------------------------------------------------------------------------- #
def test_field_constants_relationship() -> None:
    assert len(EDITABLE_FIELDS) >= 1
    assert len(DIVERGENCE_FIELDS) >= 1
    # divergence fields are a subset of editable fields
    assert set(DIVERGENCE_FIELDS) <= set(EDITABLE_FIELDS)
    # the three divergence inputs are pinned by §11 / sub-plan 04
    assert set(DIVERGENCE_FIELDS) == {
        "big_idea",
        "copy.headline",
        "art_direction.imagery_direction",
    }


# --------------------------------------------------------------------------- #
# Events & run-state vocabulary                                               #
# --------------------------------------------------------------------------- #
def test_runstate_pinned_values() -> None:
    for name in (
        "intake",
        "awaiting_strategy_approval",
        "awaiting_curation",
        "done",
        "cancelled",
        "error",
    ):
        assert RunState(name).value == name


def test_node_and_gate_run_state_maps() -> None:
    for node in ("interrogate", "research", "strategize", "verbal", "briefwrite", "seed"):
        assert isinstance(NODE_RUN_STATE[node], RunState)
    assert GATE_RUN_STATE["strategy_gate"] == RunState.awaiting_strategy_approval
    assert GATE_RUN_STATE["ideation_gate"] == RunState.awaiting_ideation
    assert GATE_RUN_STATE["curation_gate"] == RunState.awaiting_curation


def test_non_resumable_states_exact_set() -> None:
    assert set(NON_RESUMABLE_STATES) == {
        RunState.awaiting_strategy_approval,
        RunState.awaiting_ideation,
        RunState.awaiting_curation,
        RunState.done,
        RunState.cancelled,
        RunState.intake,
    }
    # error is deliberately resumable (retry after a crashed run).
    assert RunState.error not in NON_RESUMABLE_STATES


def test_event_type_constants() -> None:
    for name in (
        "run_created",
        "run_state_changed",
        "agent_started",
        "agent_completed",
        "agent_failed",
        "agent_token",
        "artifact_written",
        "direction_created",
        "direction_updated",
        "divergence_computed",
        "gate_reached",
        "gate_resolved",
        "run_cancelled",
    ):
        assert EventType(name).value == name


def test_direction_change_exact_set() -> None:
    assert {c.value for c in DirectionChange} == {
        "edit",
        "regenerate_field",
        "regenerate_sketch",
        "regenerate_sketches",
        "regenerate_moodboard_item",
        "recritique",
    }


# --------------------------------------------------------------------------- #
# Views                                                                        #
# --------------------------------------------------------------------------- #
def test_project_summary_and_event_out() -> None:
    s = ProjectSummary(id="p1", state="researching", brief_excerpt="Launch a...")
    assert s.error is None
    ev = EventOut(seq=1, type="run_created", payload={"id": "p1"}, at="2026-07-03T00:00:00Z")
    assert ev.seq == 1


def test_project_view_composes_artifacts() -> None:
    v = ProjectView(id="p1", state="awaiting_curation", brief=Brief(brief="x"))
    assert v.directions == []
    assert v.brief.brief == "x"
    # detail view carries the current interrupt payload slot
    v2 = ProjectView(id="p1", state="awaiting_strategy_approval", interrupt={"gate": "strategy"})
    assert v2.interrupt["gate"] == "strategy"


# sanity: operator import used to keep parity with state reducer tests
assert operator.add is not None
