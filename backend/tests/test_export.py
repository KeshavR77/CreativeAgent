"""Export markdown renderer tests.

Deterministic, LLM-free markdown: a Sketches section, per-tile provenance lines of
BOTH kinds, an Assets & licensing itemization, and an AI disclosure naming the
sketch/moodboard image counts. Candidate names are badged unscreened.
"""

from __future__ import annotations

from app.api.routes_export import render_export_markdown
from app.models.artifacts import (
    ArtDirectionSpec,
    ConceptPackage,
    CopyDeck,
    ImageRef,
    PaletteColor,
    Strategy,
    TypeChoice,
)

BRIEF = "Launch a sustainable sneaker brand for runners who are sick of greenwashing today."


def _gen(url, prompt="rough marker sketch") -> ImageRef:
    return ImageRef(kind="generated", url=url, provider="generated", license="AI-generated", gen_model="flux/schnell", gen_prompt=prompt)


def _sourced(url) -> ImageRef:
    return ImageRef(kind="sourced", url=url, provider="mock-pexels", license="Pexels License", source_url="https://example.com/x", attribution="Jane Doe")


def _package() -> ConceptPackage:
    art = ArtDirectionSpec(
        imagery_direction="raw honest product macro shots",
        layout_notes="asymmetric, generous whitespace",
        palette=[PaletteColor(name="Proof Green", hex="#2E7D32", role="primary")],
        typography=[TypeChoice(role="heading", family="Inter")],
        moodboard=[_gen("/g/m1.png", "moodboard tile a"), _gen("/g/m2.png", "moodboard tile b"), _sourced("/s/m3.jpg"), _sourced("/s/m4.jpg")],
    )
    return ConceptPackage(
        direction_id="dir_1",
        territory_label="Radical Transparency",
        strategy=Strategy(positioning="the anti-greenwashing running shoe", key_message="proof, not promises"),
        big_idea="Show the seams: every material traced on the shoe itself.",
        names=["Tread", "Proof"],
        sketches=[_gen("/g/s1.png"), _gen("/g/s2.png")],
        art_direction=art,
        copy=CopyDeck(headline="Nothing to hide.", cta="See the proof"),
        rationale="It converts skeptics with verifiable proof.",
    )


def test_export_has_all_required_sections() -> None:
    md = render_export_markdown([_package()], BRIEF)

    # H1 = first 8 words of the brief
    assert md.startswith("# Launch a sustainable sneaker brand for runners who\n")
    assert "## Radical Transparency" in md  # per-package H2 = territory label
    assert "### Sketches" in md
    assert "### Art direction" in md
    assert "### Copy" in md
    assert "### Why it works" in md
    assert "## Assets & licensing" in md
    assert "## AI disclosure" in md


def test_export_has_both_provenance_kinds() -> None:
    md = render_export_markdown([_package()], BRIEF)
    assert 'AI-generated via flux/schnell' in md  # generated provenance
    assert "© Jane Doe" in md  # sourced attribution
    assert "Pexels License" in md


def test_export_disclosure_counts_and_unscreened_badge() -> None:
    md = render_export_markdown([_package()], BRIEF)
    # 2 sketches + 2 moodboard tiles generated = 4 generated; 2 sourced tiles
    assert "4 AI-generated image" in md
    assert "2 sourced image" in md
    assert "unscreened" in md.lower()


def test_export_is_deterministic() -> None:
    pkg = _package()
    assert render_export_markdown([pkg], BRIEF) == render_export_markdown([pkg], BRIEF)
