"""Design-token renderers (§15).

Deterministic, LLM-free translation of a package's palette + typography into
machine-readable design tokens: a W3C-style ``tokens.json`` (every token has
``$value`` + ``$type``) and a ``tokens.css`` of custom properties. Design output
stays tokens/vector — never raster.
"""

from __future__ import annotations

import re

from app.models.artifacts import ConceptPackage


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def _unique(base: str, existing: dict, fallback: str) -> str:
    key = base or fallback
    if key not in existing:
        return key
    i = 2
    while f"{key}-{i}" in existing:
        i += 1
    return f"{key}-{i}"


def build_tokens_json(package: ConceptPackage) -> dict:
    """W3C-style design tokens ({group: {name: {$value, $type}}})."""
    art = package.art_direction
    color: dict = {}
    for i, c in enumerate(art.palette):
        key = _unique(_slug(c.role) or _slug(c.name), color, f"color-{i + 1}")
        color[key] = {"$value": c.hex, "$type": "color"}
    font: dict = {}
    for i, t in enumerate(art.typography):
        key = _unique(_slug(t.role), font, f"font-{i + 1}")
        font[key] = {"$value": t.family, "$type": "fontFamily"}
    return {"color": color, "font": font}


def build_tokens_css(package: ConceptPackage) -> str:
    """CSS custom properties mirroring ``build_tokens_json``."""
    tokens_json = build_tokens_json(package)
    lines = [":root {"]
    for prefix, group in (("color", tokens_json["color"]), ("font", tokens_json["font"])):
        for name, token in group.items():
            lines.append(f"  --{prefix}-{name}: {token['$value']};")
    lines.append("}")
    return "\n".join(lines) + "\n"
