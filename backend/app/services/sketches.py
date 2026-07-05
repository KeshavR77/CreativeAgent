"""Sketch service (§8.7, §10.7 step 3).

Produces N **distinct** exploratory concept sketches for a direction — varying
medium/angle, seeded by big_idea + territory lens, with NO brand names, logos, or
legible text. Sketches are always generated (never sourced); if the image-gen
lane is unavailable it degrades to ``placeholder`` refs (count preserved) so the
system still runs. Regeneration replaces a single slot or the whole batch.
"""

from __future__ import annotations

from app.config import get_settings
from app.models.artifacts import ImageRef
from app.services.imagegen import ImageGenUnavailable
from app.services.imagegen import generate as imagegen_generate

_MEDIUMS = (
    "rough marker sketch",
    "quick concept thumbnail",
    "loose ink gesture drawing",
    "gray-scale value study",
    "napkin thumbnail",
    "charcoal composition study",
)
_PLACEHOLDER_CAPTION = "sketch generation unavailable"


def _prompts(big_idea: str, lens: str, n: int) -> list[str]:
    return [
        f"{_MEDIUMS[i % len(_MEDIUMS)]} exploring '{big_idea}' through the lens of {lens}; "
        "no brand names, no logos, no legible text in the image"
        for i in range(n)
    ]


def _placeholder(project_id: str, direction_id: str) -> ImageRef:
    return ImageRef(
        kind="placeholder",
        url=f"/generated/{project_id}/{direction_id}/placeholder.png",
        provider="placeholder",
        license="none",
        caption=_PLACEHOLDER_CAPTION,
    )


def generate(direction_id: str, big_idea: str, lens: str, *, project_id: str, n: int | None = None) -> list[ImageRef]:
    count = n if n is not None else get_settings().SKETCH_COUNT
    prompts = _prompts(big_idea, lens, count)
    try:
        return imagegen_generate(prompts, project_id=project_id, direction_id=direction_id)
    except ImageGenUnavailable:
        return [_placeholder(project_id, direction_id) for _ in range(count)]


def regenerate_single(
    current: list[ImageRef],
    index: int,
    direction_id: str,
    big_idea: str,
    lens: str,
    *,
    project_id: str,
    prompt: str | None = None,
) -> list[ImageRef]:
    result = list(current)
    new_prompt = prompt or _prompts(big_idea, lens, len(current))[index]
    try:
        (ref,) = imagegen_generate([new_prompt], project_id=project_id, direction_id=direction_id)
    except ImageGenUnavailable:
        ref = _placeholder(project_id, direction_id)
    result[index] = ref
    return result


def regenerate_batch(
    current: list[ImageRef], direction_id: str, big_idea: str, lens: str, *, project_id: str
) -> list[ImageRef]:
    return generate(direction_id, big_idea, lens, project_id=project_id, n=len(current))
