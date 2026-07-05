"""Checkpointer serde registers our artifact types (Stage 09 follow-up).

Verifies the msgpack allowlist names our artifact types explicitly (so the
"Deserializing unregistered type ..." forward-compat warning is gone) AND that a
fully-nested artifact round-trips as its real model types — a blocked/unlisted
type would silently come back as a raw dict, so isinstance is the completeness
check.
"""

from __future__ import annotations

from app.models.artifacts import (
    Annotation,
    ArtDirectionSpec,
    CopyDeck,
    CostRecord,
    CritiqueScore,
    Direction,
    ImageRef,
    PaletteColor,
    Territory,
    TypeChoice,
)
from app.storage.checkpoint import artifact_types, make_serde

_CASE = " ".join(["against"] * 55)  # case_against must be >= 50 words


def _generated_image() -> ImageRef:
    return ImageRef(
        kind="generated",
        url="/generated/x.png",
        provider="mock-image",
        license="AI-generated",
        gen_model="mock-diffusion",
        gen_prompt="a bold poster",
    )


def _full_direction() -> Direction:
    return Direction(
        id="dir-abc",
        territory=Territory(label="Rebel Optimism", lens="defiant hope", description="d"),
        big_idea="Dare to glow",
        brain="mock",
        art_direction=ArtDirectionSpec(
            imagery_direction="sun-drenched portraits",
            mood_descriptors=["bold", "warm"],
            layout_notes="asymmetric",
            palette=[PaletteColor(name="Ember", hex="#FF5522", role="primary")],
            typography=[TypeChoice(role="display", family="Grotesk", fallback="sans", weights=["400", "700"])],
            moodboard=[_generated_image() for _ in range(4)],
        ),
        copy=CopyDeck(headline="Glow up", subhead="s", body="b", taglines=["t"], cta="Join"),
        sketches=[_generated_image()],
        critique=CritiqueScore(
            distinctiveness=4,
            strategic_fit=4,
            memorability=3,
            audience_resonance=4,
            feasibility=5,
            case_against=_CASE,
            verdict="revise",
            critic_model="mock-critic",
        ),
        annotations=[Annotation(text="a note", author="human")],
    )


def test_allowlist_registers_artifact_types_explicitly() -> None:
    allow = make_serde()._allowed_msgpack_modules
    assert allow not in (True, None)  # a specific allowlist, not the permissive (warning) default
    for name in ("Direction", "CritiqueScore", "ImageRef", "CostRecord", "ConceptPackage", "Strategy", "Territory"):
        assert ("app.models.artifacts", name) in allow


def test_introspection_covers_the_artifact_models() -> None:
    names = {t.__name__ for t in artifact_types()}
    assert {
        "Brief", "Direction", "CritiqueScore", "ImageRef", "ArtDirectionSpec",
        "CopyDeck", "PaletteColor", "TypeChoice", "CostRecord", "ConceptPackage",
        "Strategy", "VerbalIdentity", "CreativeBrief", "Territory", "Annotation",
        "SourceRef", "ResearchDossier",
    } <= names


def test_serde_round_trips_nested_artifacts_as_real_types_not_dicts() -> None:
    serde = make_serde()
    original = {
        "directions": [_full_direction()],
        "costs": [CostRecord(agent="explore", model="mock", input_tokens=3, output_tokens=1)],
    }
    restored = serde.loads_typed(serde.dumps_typed(original))

    d = restored["directions"][0]
    # A blocked/unregistered type silently degrades to a dict — assert every nested
    # artifact comes back as its model type.
    assert isinstance(d, Direction)
    assert isinstance(d.territory, Territory)
    assert isinstance(d.critique, CritiqueScore)
    assert isinstance(d.art_direction, ArtDirectionSpec)
    assert isinstance(d.art_direction.palette[0], PaletteColor)
    assert isinstance(d.art_direction.typography[0], TypeChoice)
    assert isinstance(d.art_direction.moodboard[0], ImageRef)
    assert isinstance(d.sketches[0], ImageRef)
    assert isinstance(d.annotations[0], Annotation)
    assert isinstance(restored["costs"][0], CostRecord)
    assert d == _full_direction()  # full fidelity
