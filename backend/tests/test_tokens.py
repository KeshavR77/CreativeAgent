"""Design-token renderer tests.

Deterministic, LLM-free tokens from a package's palette/typography: W3C-shaped
`tokens.json` (every token has `$value` + `$type`) and parseable `tokens.css`
custom properties.
"""

from __future__ import annotations

from app.models.artifacts import (
    ArtDirectionSpec,
    ConceptPackage,
    CopyDeck,
    PaletteColor,
    Strategy,
    TypeChoice,
)
from app.services import tokens


def _package() -> ConceptPackage:
    art = ArtDirectionSpec(
        imagery_direction="raw honest product macro shots",
        palette=[
            PaletteColor(name="Proof Green", hex="#2E7D32", role="primary"),
            PaletteColor(name="Trail Clay", hex="#A1502B", role="secondary"),
            PaletteColor(name="Dawn Grey", hex="#E0E0E0", role="accent"),
        ],
        typography=[
            TypeChoice(role="heading", family="Inter"),
            TypeChoice(role="body", family="Georgia"),
        ],
        moodboard=[],
    )
    return ConceptPackage(
        direction_id="dir_1",
        territory_label="Radical Transparency",
        strategy=Strategy(positioning="anti-greenwashing", key_message="proof not promises"),
        big_idea="Show the seams.",
        names=["Tread"],
        sketches=[],
        art_direction=art,
        copy=CopyDeck(headline="Nothing to hide."),
        rationale="It converts skeptics with proof.",
    )


def test_tokens_json_is_w3c_shaped() -> None:
    tj = tokens.build_tokens_json(_package())

    assert "color" in tj
    assert len(tj["color"]) == 3
    for token in tj["color"].values():
        assert token["$type"] == "color"
        assert token["$value"].startswith("#") and len(token["$value"]) == 7

    assert "font" in tj
    for token in tj["font"].values():
        assert token["$type"] == "fontFamily"
        assert isinstance(token["$value"], str) and token["$value"]


def test_tokens_css_has_parseable_custom_properties() -> None:
    css = tokens.build_tokens_css(_package())

    assert ":root {" in css and css.rstrip().endswith("}")
    assert "--color-primary: #2E7D32;" in css
    assert "--font-heading: Inter;" in css
    assert "--font-body: Georgia;" in css
    # every property line is `  --name: value;`
    body = [ln.strip() for ln in css.splitlines() if ln.strip().startswith("--")]
    assert body
    for line in body:
        assert line.startswith("--") and line.endswith(";") and ":" in line


def test_tokens_are_deterministic() -> None:
    pkg = _package()
    assert tokens.build_tokens_json(pkg) == tokens.build_tokens_json(pkg)
    assert tokens.build_tokens_css(pkg) == tokens.build_tokens_css(pkg)
