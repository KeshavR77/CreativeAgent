"""Provenance-enforcement tests.

No ImageRef failing its per-kind rule can reach state, a view, or export-bound
assembly — provenance is validated at the model boundary (unconstructible when
violated), and every image caller only emits complete refs (dropping the rest).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.artifacts import ImageRef
from app.services import imagesource, moodboard, sketches


def _complete(ref: ImageRef) -> bool:
    if ref.kind == "generated":
        return bool(ref.gen_model and ref.gen_prompt and ref.provider and ref.license)
    if ref.kind == "sourced":
        return bool(ref.source_url and ref.attribution and ref.provider and ref.license)
    return bool(ref.provider and ref.license)  # placeholder


def test_incomplete_imagerefs_are_unconstructible() -> None:
    with pytest.raises(ValidationError):  # generated without gen_model/gen_prompt
        ImageRef(kind="generated", url="/x.png", provider="generated", license="AI-generated")
    with pytest.raises(ValidationError):  # sourced without source_url/attribution
        ImageRef(kind="sourced", url="/x.jpg", provider="pexels", license="Pexels License")
    with pytest.raises(ValidationError):  # base64 into state is forbidden
        ImageRef(kind="placeholder", url="data:image/png;base64,AAAA", provider="p", license="none")


def test_sketches_are_complete_and_never_sourced(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    for ref in sketches.generate("d", "idea", "lens", project_id="p"):
        assert _complete(ref)
        assert ref.kind != "sourced"  # sketches are always generated / placeholder


def test_moodboard_items_are_all_complete(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")
    for ref in moodboard.build("d", ["earthy", "honest"], "raw materials", project_id="p"):
        assert _complete(ref)


def test_imagesource_drops_provenance_incomplete_corpus_entries(clean_env, monkeypatch) -> None:
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")
    corpus = [
        {"id": "ok", "provider": "pexels", "url": "/a.jpg", "source_url": "/a", "license": "CC0", "attribution": "X", "tags": ["trail"], "description": "trail"},
        {"id": "bad", "provider": "pexels", "url": "/b.jpg", "source_url": "/b", "license": "CC0", "tags": ["trail"], "description": "trail"},  # no attribution
    ]
    monkeypatch.setattr(imagesource, "_load_corpus", lambda: corpus)

    refs = imagesource.search("trail", 5)
    assert refs  # the valid one is returned
    assert all(_complete(r) for r in refs)
    assert "/b.jpg" not in {r.url for r in refs}  # the incomplete entry was dropped
