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
from app.services.imagegen import generate_reliable as imagegen_generate

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
        "no brand names, no logos, no legible text in the image, "
        "no words, no lettering, no characters or typography of any kind, in any language"
        for i in range(n)
    ]


def _placeholder(project_id: str, direction_id: str) -> ImageRef:
    from app.services.imagegen import ensure_placeholder

    return ImageRef(
        kind="placeholder",
        url=ensure_placeholder(project_id, direction_id, "placeholder.png"),
        provider="placeholder",
        license="none",
        caption=_PLACEHOLDER_CAPTION,
    )


def generate(direction_id: str, big_idea: str, lens: str, *, project_id: str, n: int | None = None) -> list[ImageRef]:
    count = n if n is not None else get_settings().SKETCH_COUNT
    prompts = _prompts(big_idea, lens, count)
    try:
        # generate_reliable guarantees exactly `count` real refs when the lane is
        # enabled — no placeholders in a real run. Placeholders only appear on the
        # keyless path (lane disabled), which raises below.
        return list(imagegen_generate(prompts, project_id=project_id, direction_id=direction_id))
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


# regenerate_single/regenerate_batch above resolve their images through
# generate_reliable too (imagegen_generate is bound to it), so a single-tile
# regenerate in the Cockpit also yields a real image, never a placeholder.


def regenerate_batch(
    current: list[ImageRef], direction_id: str, big_idea: str, lens: str, *, project_id: str
) -> list[ImageRef]:
    return generate(direction_id, big_idea, lens, project_id=project_id, n=len(current))
