"""Sketch / moodboard regeneration op tests.

Visual regeneration updates only the visuals: it NEVER marks the critique stale
and NEVER re-runs divergence (unlike the text ops). Image lanes are enabled here
so regeneration produces real generated/sourced refs.
"""

from __future__ import annotations

from app.models.events import RunState


def _enable_lanes(clean_env):
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")


async def _to_curation(rm, brief, pid: str = "p1") -> None:
    await (await rm.start(pid, brief))
    await (await rm.resume(pid, {"action": "approve"}))


def _find(view, did):
    return next(d for d in view.directions if d.id == did)


def _divergence_events(rm, pid: str = "p1") -> int:
    return sum(1 for e in rm.events.since(pid, 0) if e.type == "divergence_computed")


async def test_regenerate_single_sketch_has_no_side_effects(graph_manager, sneaker_brief, clean_env) -> None:
    _enable_lanes(clean_env)
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    d = (await rm.get_view("p1")).directions[0]
    did, original, before_stale, before_div = d.id, list(d.sketches), d.critique_stale, _divergence_events(rm)

    await (await rm.resume("p1", {"op": "regenerate_sketch", "direction_id": did, "index": 0}))

    d2 = _find(await rm.get_view("p1"), did)
    assert d2.sketches[0] != original[0]  # index 0 replaced
    assert d2.sketches[1:] == original[1:]  # others untouched
    assert d2.critique_stale == before_stale  # critique NOT staled
    assert _divergence_events(rm) == before_div  # divergence NOT re-run
    assert registry.get("p1").state == RunState.awaiting_curation.value


async def test_regenerate_sketches_batch_replaces_all(graph_manager, sneaker_brief, clean_env) -> None:
    _enable_lanes(clean_env)
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    d = (await rm.get_view("p1")).directions[0]
    did, original, before_div = d.id, list(d.sketches), _divergence_events(rm)

    await (await rm.resume("p1", {"op": "regenerate_sketches", "direction_id": did}))

    d2 = _find(await rm.get_view("p1"), did)
    assert {s.url for s in d2.sketches}.isdisjoint({s.url for s in original})  # all fresh
    assert _divergence_events(rm) == before_div


async def test_regenerate_moodboard_item_kind_swap(graph_manager, sneaker_brief, clean_env) -> None:
    _enable_lanes(clean_env)
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    d = (await rm.get_view("p1")).directions[0]
    did = d.id
    gi = next(i for i, img in enumerate(d.art_direction.moodboard) if img.kind == "generated")
    before_div = _divergence_events(rm)

    await (await rm.resume("p1", {"op": "regenerate_moodboard_item", "direction_id": did, "index": gi, "kind": "sourced"}))

    d2 = _find(await rm.get_view("p1"), did)
    swapped = d2.art_direction.moodboard[gi]
    assert swapped.kind == "sourced"
    assert swapped.source_url and swapped.attribution  # provenance for the new lane
    assert d2.critique_stale == d.critique_stale
    assert _divergence_events(rm) == before_div
