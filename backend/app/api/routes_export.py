"""Export + design-token API and the markdown renderer (§13/§15).

The product's actual deliverable: a deterministic, LLM-free markdown concept
package with full per-image provenance, plus W3C design tokens / CSS. No model
calls anywhere here. Every image is provenance-complete by construction (the
ImageRef model boundary), so the export never surfaces an unprovenanced image.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.models.artifacts import ConceptPackage, ImageRef
from app.services import tokens as tokens_svc

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
# markdown renderer (pure)                                                     #
# --------------------------------------------------------------------------- #
def _sketch_line(img: ImageRef) -> str:
    if img.kind == "generated":
        return f'- ![sketch]({img.url}) — AI-generated via {img.gen_model}, prompt: "{img.gen_prompt}"'
    if img.kind == "placeholder":
        return f"- (sketch unavailable) — {img.caption or 'placeholder'}"
    return f"- ![sketch]({img.url})"


def _moodboard_line(img: ImageRef) -> str:
    if img.kind == "generated":
        return f'- ![tile]({img.url}) — AI-generated via {img.gen_model} — prompt: "{img.gen_prompt}"'
    if img.kind == "sourced":
        return f"- ![tile]({img.url}) — {img.provider}, {img.license}, © {img.attribution} ({img.source_url})"
    return f"- ![tile]({img.url}) — {img.caption or 'placeholder'}"


def _asset_line(kind_label: str, img: ImageRef) -> str:
    if img.kind == "sourced":
        prov = f"{img.license}, © {img.attribution}"
    elif img.kind == "generated":
        prov = f"{img.license} ({img.gen_model})"
    else:
        prov = "placeholder"
    return f"- {kind_label} ({img.kind}): {img.url} — {prov}"


def _render_package(pkg: ConceptPackage) -> list[str]:
    art = pkg.art_direction
    lines = [f"## {pkg.territory_label}", ""]
    if pkg.names:
        lines += [f"**Candidate names (unscreened):** {', '.join(pkg.names)}", ""]
    lines += ["### Strategy", pkg.strategy.positioning, "", f"_{pkg.strategy.key_message}_", ""]
    lines += ["### Big idea", pkg.big_idea, ""]
    lines += ["### Sketches", ""]
    lines += [_sketch_line(s) for s in pkg.sketches] or ["_(none)_"]
    lines += ["", "### Art direction", ""]
    if art.palette:
        lines += ["**Palette:** " + ", ".join(f"{c.name} `{c.hex}`" for c in art.palette), ""]
    if art.typography:
        lines += ["**Typography:** " + ", ".join(f"{t.role}: {t.family}" for t in art.typography), ""]
    lines += [art.imagery_direction, ""]
    if art.layout_notes:
        lines += [art.layout_notes, ""]
    lines += ["#### Moodboard", ""]
    lines += [_moodboard_line(m) for m in art.moodboard] or ["_(none)_"]
    lines += ["", "### Copy", f"**{pkg.copy.headline}**"]
    if pkg.copy.subhead:
        lines.append(pkg.copy.subhead)
    if pkg.copy.body:
        lines.append(pkg.copy.body)
    if pkg.copy.cta:
        lines.append(f"→ {pkg.copy.cta}")
    lines += ["", "### Why it works", pkg.rationale, ""]
    return lines


def render_export_markdown(packages: list[ConceptPackage], brief_text: str) -> str:
    """Deterministic markdown concept doc for the given packages."""
    h1 = " ".join(brief_text.split()[:8])
    lines = [f"# {h1}", ""]

    total_generated = total_sourced = 0
    for pkg in packages:
        lines += _render_package(pkg)
        for img in list(pkg.sketches) + list(pkg.art_direction.moodboard):
            if img.kind == "generated":
                total_generated += 1
            elif img.kind == "sourced":
                total_sourced += 1

    lines += ["## Assets & licensing", ""]
    for pkg in packages:
        lines += [_asset_line("Sketch", s) for s in pkg.sketches]
        lines += [_asset_line("Moodboard", m) for m in pkg.art_direction.moodboard]
    lines += [""]

    lines += [
        "---",
        "## AI disclosure",
        (
            f"This export contains {total_generated} AI-generated image(s) and "
            f"{total_sourced} sourced image(s). Sketch generation and moodboard generation are "
            "AI-assisted and labeled per image above. Candidate brand names are unscreened for "
            "trademark and must be cleared before use."
        ),
        "",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# endpoints                                                                    #
# --------------------------------------------------------------------------- #
async def _packages_and_brief(request: Request, project_id: str, direction_id: str | None):
    view = await request.app.state.run_manager.get_view(project_id)
    if view is None:
        raise HTTPException(status_code=404, detail="unknown project")
    packages = list(view.packages)
    if direction_id:
        packages = [p for p in packages if p.direction_id == direction_id]
    if not packages:
        raise HTTPException(status_code=404, detail="no packages (project not finalized?)")
    brief = view.brief.brief if view.brief is not None else ""
    return packages, brief


@router.get("/projects/{project_id}/export.md")
async def export_markdown(project_id: str, request: Request, direction_id: str | None = None) -> Response:
    packages, brief = await _packages_and_brief(request, project_id, direction_id)
    return Response(content=render_export_markdown(packages, brief), media_type="text/markdown")


@router.get("/projects/{project_id}/tokens.json")
async def tokens_json(project_id: str, request: Request, direction_id: str | None = None) -> dict:
    packages, _ = await _packages_and_brief(request, project_id, direction_id)
    return tokens_svc.build_tokens_json(packages[0])


@router.get("/projects/{project_id}/tokens.css")
async def tokens_css(project_id: str, request: Request, direction_id: str | None = None) -> Response:
    packages, _ = await _packages_and_brief(request, project_id, direction_id)
    return Response(content=tokens_svc.build_tokens_css(packages[0]), media_type="text/css")
