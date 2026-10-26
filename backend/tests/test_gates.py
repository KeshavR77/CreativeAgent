"""Curation-gate routing tests.

Drives the RunManager to the curation gate and exercises the op routing table:
promote self-loops; finalize requires a promotion (and then produces packages);
edits to a divergence field re-run divergence, edits to a non-divergence field
do not.
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


async def test_promote_self_loops_and_stays_at_gate(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    await (await rm.resume("p1", {"op": "promote", "direction_id": did}))

    assert registry.get("p1").state == RunState.awaiting_curation.value  # re-interrupt
    assert _find(await rm.get_view("p1"), did).status == "promoted"


async def test_finalize_requires_a_promotion(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)

    # finalize with nothing promoted -> stays at the gate
    await (await rm.resume("p1", {"op": "finalize"}))
    assert registry.get("p1").state == RunState.awaiting_curation.value

    # promote then finalize -> refine -> package -> END
    did = (await rm.get_view("p1")).directions[0].id
    await (await rm.resume("p1", {"op": "promote", "direction_id": did}))
    await (await rm.resume("p1", {"op": "finalize"}))

    assert registry.get("p1").state == RunState.done.value
    view = await rm.get_view("p1")
    assert view.packages
    assert any(p.direction_id == did for p in view.packages)


async def test_edit_divergence_field_reruns_divergence(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    before = _divergence_events(rm)
    await (await rm.resume("p1", {"op": "edit", "direction_id": did, "field": "big_idea", "value": "a distinct fresh idea"}))
    assert _divergence_events(rm) == before + 1  # divergence field -> recomputed
    assert registry.get("p1").state == RunState.awaiting_curation.value
    assert _find(await rm.get_view("p1"), did).critique_stale is True


async def test_edit_non_divergence_field_skips_divergence(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    before = _divergence_events(rm)
    await (await rm.resume("p1", {"op": "edit", "direction_id": did, "field": "copy.subhead", "value": "a new subhead"}))
    assert _divergence_events(rm) == before  # non-divergence field -> no recompute
    d = _find(await rm.get_view("p1"), did)
    assert d.copy.subhead == "a new subhead"
    assert d.critique_stale is True


async def test_kill_self_loops_and_marks_status(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    await (await rm.resume("p1", {"op": "kill", "direction_id": did}))

    assert registry.get("p1").state == RunState.awaiting_curation.value  # re-interrupt
    assert _find(await rm.get_view("p1"), did).status == "killed"


async def test_annotate_appends_note_and_self_loops(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    await (await rm.resume("p1", {"op": "annotate", "direction_id": did, "text": "push it harder", "author": "cd"}))

    assert registry.get("p1").state == RunState.awaiting_curation.value
    d = _find(await rm.get_view("p1"), did)
    assert any(a.text == "push it harder" and a.author == "cd" for a in d.annotations)


async def test_recritique_clears_staleness_via_divergence(graph_manager, sneaker_brief) -> None:
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    # make the critique stale via a non-divergence edit, then recritique
    await (await rm.resume("p1", {"op": "edit", "direction_id": did, "field": "copy.subhead", "value": "x"}))
    assert _find(await rm.get_view("p1"), did).critique_stale is True

    before = _divergence_events(rm)
    await (await rm.resume("p1", {"op": "recritique", "direction_id": did}))
    assert _divergence_events(rm) == before + 1  # recritique routes via divergence
    assert _find(await rm.get_view("p1"), did).critique_stale is False  # staleness cleared
