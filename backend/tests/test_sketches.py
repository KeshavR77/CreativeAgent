"""Sketch service tests.

Sketches are always generated (never sourced): SKETCH_COUNT distinct prompts when
the image-gen lane is enabled, or a placeholder fallback (count preserved) when
it is unavailable. Single/batch regeneration replaces the right slots.
"""

from __future__ import annotations

from app.services import sketches


def test_generate_produces_sketch_count_distinct_generated(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")  # enable the generated lane
    refs = sketches.generate("dir1", "trace every material on the shoe", "proof over promises", project_id="p1")
    assert len(refs) == 3  # SKETCH_COUNT default
    assert all(r.kind == "generated" for r in refs)
    assert all(r.provider == "generated" and r.license == "AI-generated" for r in refs)
    assert all(r.gen_model and r.gen_prompt for r in refs)
    assert len({r.gen_prompt for r in refs}) == 3  # distinct prompts
    # never base64 in state
    assert all(not r.url.startswith("data:") for r in refs)


def test_generate_placeholder_fallback_when_disabled(clean_env) -> None:
    # image gen disabled (keyless) -> placeholder fallback, count preserved
    refs = sketches.generate("dir1", "a big idea", "a lens", project_id="p1")
    assert len(refs) == 3
    assert all(r.kind == "placeholder" for r in refs)
    assert all("unavailable" in (r.caption or "").lower() for r in refs)


def test_single_regen_replaces_exactly_one(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    original = sketches.generate("dir1", "idea", "lens", project_id="p1")
    regenerated = sketches.regenerate_single(original, 1, "dir1", "idea", "lens", project_id="p1")

    assert len(regenerated) == len(original)
    assert regenerated[0] == original[0]  # others byte-identical
    assert regenerated[2] == original[2]
    assert regenerated[1] != original[1]  # only index 1 replaced


def test_batch_regen_replaces_whole_list(clean_env) -> None:
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    original = sketches.generate("dir1", "idea", "lens", project_id="p1")
    regenerated = sketches.regenerate_batch(original, "dir1", "idea", "lens", project_id="p1")

    assert len(regenerated) == len(original)
    assert {r.url for r in regenerated}.isdisjoint({r.url for r in original})  # all fresh


def test_single_regen_placeholder_when_disabled(clean_env) -> None:
    original = sketches.generate("dir1", "idea", "lens", project_id="p1")  # placeholders
    regenerated = sketches.regenerate_single(original, 0, "dir1", "idea", "lens", project_id="p1")
    assert len(regenerated) == len(original)
    assert regenerated[0].kind == "placeholder"
