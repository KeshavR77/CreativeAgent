"""Hybrid moodboard service.

Builds a ``MOODBOARD_SIZE`` board that is hybrid by construction: a generated
share (``round(size * ratio)``) + a sourced share. If one lane is down its share
is redirected to the live lane; if both are down the board is all placeholders.
Every item is independently provenance-complete; a shortfall (dropped incomplete
refs) is backfilled with placeholders so the board always reaches ``size``. Items
are deterministically shuffled — lanes are never visually segregated.
"""

from __future__ import annotations

import hashlib

from app.config import get_settings
from app.models.artifacts import ImageRef
from app.services import imagegen, imagesource

_PLACEHOLDER_CAPTION = "moodboard image unavailable"


def _placeholder(project_id: str, direction_id: str) -> ImageRef:
    return ImageRef(
        kind="placeholder",
        url=imagegen.ensure_placeholder(project_id, direction_id, "moodboard-placeholder.png"),
        provider="placeholder",
        license="none",
        caption=_PLACEHOLDER_CAPTION,
    )


def _gen_prompts(moods: list[str], imagery: str, palette, n: int) -> list[str]:
    palette_str = ", ".join(getattr(c, "hex", str(c)) for c in (palette or []))
    base = f"moodboard tile — {imagery}; mood: {', '.join(moods)}"
    if palette_str:
        base += f"; palette {palette_str}"
    return [
        f"{base}; variation {i + 1}; no brand names, no logos, no legible text, "
        "no words, no lettering, no characters or typography of any kind, in any language"
        for i in range(n)
    ]


def _src_queries(moods: list[str], imagery: str) -> list[str]:
    queries = [imagery]
    if moods:
        queries.append(" ".join(moods[:2]))
    if len(moods) > 2:
        queries.append(moods[-1])
    return queries[:3]


def _gen_share(project_id: str, direction_id: str, moods, imagery, palette, n: int) -> list[ImageRef]:
    try:
        # generate_reliable returns exactly n real tiles when the lane is enabled.
        return imagegen.generate_reliable(
            _gen_prompts(moods, imagery, palette, n), project_id=project_id, direction_id=direction_id
        )
    except imagegen.ImageGenUnavailable:
        return []


def _src_share(moods: list[str], imagery: str, n: int) -> list[ImageRef]:
    seen: set[str] = set()
    refs: list[ImageRef] = []
    for query in _src_queries(moods, imagery):
        if len(refs) >= n:
            break
        try:
            for ref in imagesource.search(query, n - len(refs)):
                if ref.url not in seen:
                    seen.add(ref.url)
                    refs.append(ref)
        except imagesource.ImageSourceUnavailable:
            break
    return refs[:n]


def _shuffle(items: list[ImageRef], seed: str) -> list[ImageRef]:
    """Deterministic position-permutation (stable regardless of the random image
    filenames) so generated/sourced lanes are interleaved, not segregated."""
    order = sorted(range(len(items)), key=lambda i: hashlib.md5(f"{seed}:{i}".encode()).hexdigest())
    return [items[i] for i in order]


def build(direction_id, moods, imagery, *, project_id, palette=None, size=None, ratio=None) -> list[ImageRef]:
    settings = get_settings()
    size = size if size is not None else settings.MOODBOARD_SIZE
    ratio = ratio if ratio is not None else settings.MOODBOARD_GENERATED_RATIO
    gen_on = settings.image_gen_enabled
    src_on = settings.image_source_enabled

    if not gen_on and not src_on:
        return [_placeholder(project_id, direction_id) for _ in range(size)]

    n_gen = round(size * ratio) if gen_on else 0
    n_src = (size - n_gen) if src_on else 0
    shortfall = size - (n_gen + n_src)  # a downed lane's share -> redirect to the live lane
    if shortfall > 0:
        if gen_on:
            n_gen += shortfall
        elif src_on:
            n_src += shortfall

    items: list[ImageRef] = []
    if n_gen > 0:
        items += _gen_share(project_id, direction_id, moods, imagery, palette, n_gen)
    if n_src > 0:
        items += _src_share(moods, imagery, n_src)

    # Backfill any shortfall (e.g. the sourced lane under-delivered) to reach size.
    # When the generation lane is live, regenerate REAL tiles rather than showing
    # placeholders — a real run has no placeholder tiles.
    if len(items) < size and gen_on:
        items += _gen_share(project_id, direction_id, moods, imagery, palette, size - len(items))
    while len(items) < size:
        items.append(_placeholder(project_id, direction_id))
    return _shuffle(items[:size], direction_id)


def regenerate_slot(
    current: list[ImageRef],
    index: int,
    direction_id,
    moods,
    imagery,
    *,
    project_id,
    palette=None,
    kind: str | None = None,
    prompt: str | None = None,
) -> list[ImageRef]:
    """Regenerate a single slot. ``kind`` optionally forces generated<->sourced;
    otherwise the slot keeps its current kind. ``prompt`` is ignored for sourced."""
    result = list(current)
    target_kind = kind or current[index].kind
    ref: ImageRef | None = None
    if target_kind == "generated":
        gen_prompt = prompt or _gen_prompts(moods, imagery, palette, 1)[0]
        try:
            (ref,) = imagegen.generate_reliable([gen_prompt], project_id=project_id, direction_id=direction_id)
        except imagegen.ImageGenUnavailable:
            ref = None
    elif target_kind == "sourced":
        got = _src_share(moods, imagery, 1)
        ref = got[0] if got else None
    result[index] = ref if ref is not None else _placeholder(project_id, direction_id)
    return result
