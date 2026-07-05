"""Single-field regeneration tests (Stage 04, §12.2/§16).

Regenerating one field marks the critique stale and recomputes divergence ONLY
when the regenerated field is a divergence field; a non-editable field is a no-op.
"""

from __future__ import annotations

from app.models.events import RunState


async def _to_curation(rm, brief, pid: str = "p1") -> None:
    await (await rm.start(pid, brief))
    await (await rm.resume(pid, {"action": "approve"}))


def _find(view, did):
    return next(d for d in view.directions if d.id == did)


def _divergence_events(rm, pid: str = "p1") -> int:
    return sum(1 for e in rm.events.since(pid, 0) if e.type == "divergence_computed")


async def test_regenerate_divergence_field_reruns_divergence(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    before = _divergence_events(rm)
    await (await rm.resume("p1", {"op": "regenerate_field", "direction_id": did, "field": "big_idea"}))

    assert _divergence_events(rm) == before + 1
    assert registry.get("p1").state == RunState.awaiting_curation.value
    assert _find(await rm.get_view("p1"), did).critique_stale is True


async def test_regenerate_non_divergence_field_skips_divergence(graph_manager, sneaker_brief) -> None:
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    before = _divergence_events(rm)
    await (await rm.resume("p1", {"op": "regenerate_field", "direction_id": did, "field": "copy.subhead"}))

    assert _divergence_events(rm) == before
    assert _find(await rm.get_view("p1"), did).critique_stale is True


async def test_regenerate_rejects_non_editable_field(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    # `brain` is not an editable field -> no-op self-loop, critique not touched
    await (await rm.resume("p1", {"op": "regenerate_field", "direction_id": did, "field": "brain"}))

    assert registry.get("p1").state == RunState.awaiting_curation.value
    assert _find(await rm.get_view("p1"), did).critique_stale is False
