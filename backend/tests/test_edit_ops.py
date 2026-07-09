"""Curation edit/fork/merge op tests (Stage 04, §12.2/§16).

Patch application across editable fields (critique goes stale); fork lineage
(parent_id + lens_tweak, freshly critiqued); merge (merged_from + parents
marked merged_away, merged direction critiqued).
"""

from __future__ import annotations

import pytest


async def _to_curation(rm, brief, pid: str = "p1") -> None:
    await (await rm.start(pid, brief))
    await (await rm.resume(pid, {"action": "approve"}))


def _find(view, did):
    return next(d for d in view.directions if d.id == did)


@pytest.mark.parametrize(
    "field,value,getter",
    [
        ("big_idea", "trace every material on the shoe itself", lambda d: d.big_idea),
        ("copy.headline", "Nothing to hide.", lambda d: d.copy.headline),
        ("copy.cta", "See the proof", lambda d: d.copy.cta),
        ("art_direction.imagery_direction", "raw, honest product macro shots", lambda d: d.art_direction.imagery_direction),
    ],
)
async def test_edit_applies_patch_and_marks_stale(graph_manager, sneaker_brief, field, value, getter) -> None:
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id

    await (await rm.resume("p1", {"op": "edit", "direction_id": did, "field": field, "value": value}))

    d = _find(await rm.get_view("p1"), did)
    assert getter(d) == value
    assert d.critique_stale is True


async def test_edit_rejects_non_editable_field(graph_manager, sneaker_brief) -> None:
    rm, registry = graph_manager
    await _to_curation(rm, sneaker_brief)
    did = (await rm.get_view("p1")).directions[0].id
    before = _find(await rm.get_view("p1"), did)

    # `status` is not an editable field -> no-op, stays at the gate
    await (await rm.resume("p1", {"op": "edit", "direction_id": did, "field": "status", "value": "promoted"}))

    d = _find(await rm.get_view("p1"), did)
    assert d.status == before.status  # unchanged
    assert d.critique_stale is False


def test_regenerate_big_idea_keeps_brain_truthful(monkeypatch) -> None:
    """Regenerating big_idea updates `brain` to the ideator that produced the new
    idea — a regenerated value must not carry the stale original brain."""
    from app.graph import curation, exploration
    from app.models.artifacts import ArtDirectionSpec, CopyDeck, Direction, Territory

    monkeypatch.setattr(curation, "get_stream_writer", lambda: (lambda *a, **k: None))
    monkeypatch.setattr(
        exploration,
        "ideate_one",
        lambda pid, terr, lens_tweak=None, brief_context="": ("a freshly regenerated idea", "claude_high_temp"),
    )
    d = Direction(
        id="dir-x",
        territory=Territory(label="T", lens="lens"),
        big_idea="the old idea",
        brain="mock",
        art_direction=ArtDirectionSpec(imagery_direction="img"),
        copy=CopyDeck(headline="h"),
        sketches=[],
    )
    cmd = curation._regenerate_field("p1", [d], {"direction_id": "dir-x", "field": "big_idea"})
    updated = cmd.update["directions"][0]
    assert updated.big_idea == "a freshly regenerated idea"
    assert updated.brain == "claude_high_temp"  # brain follows the regenerating ideator
    assert updated.critique_stale is True  # a text change stales the critique


async def test_fork_creates_critiqued_child_with_lineage(graph_manager, sneaker_brief) -> None:
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    view = await rm.get_view("p1")
    parent_id = view.directions[0].id
    n_before = len(view.directions)

    await (await rm.resume("p1", {"op": "fork", "direction_id": parent_id, "lens_tweak": "louder and angrier"}))

    view2 = await rm.get_view("p1")
    assert len(view2.directions) == n_before + 1
    child = next(d for d in view2.directions if d.parent_id == parent_id)
    assert child.lens_tweak == "louder and angrier"
    assert child.critique is not None  # forked child is independently critiqued


async def test_merge_combines_and_marks_parents_merged_away(graph_manager, sneaker_brief) -> None:
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    view = await rm.get_view("p1")
    ids = [d.id for d in view.directions[:2]]

    await (
        await rm.resume(
            "p1",
            {
                "op": "merge",
                "direction_ids": ids,
                "field_choices": {"big_idea": ids[0], "copy": ids[1], "art_direction": ids[0]},
            },
        )
    )

    view2 = await rm.get_view("p1")
    merged = next(d for d in view2.directions if d.merged_from)
    assert set(merged.merged_from) == set(ids)
    assert merged.critique is not None
    parents = [d for d in view2.directions if d.id in ids]
    assert all(p.status == "merged_away" for p in parents)


async def test_merge_honors_granular_dotted_field_choices(graph_manager, sneaker_brief) -> None:
    rm, _ = graph_manager
    await _to_curation(rm, sneaker_brief)
    view = await rm.get_view("p1")
    a, b = view.directions[0], view.directions[1]

    # source big_idea from parent A but copy.headline from parent B (different parents per field)
    await (
        await rm.resume(
            "p1",
            {"op": "merge", "direction_ids": [a.id, b.id], "field_choices": {"big_idea": a.id, "copy.headline": b.id}},
        )
    )

    merged = next(d for d in (await rm.get_view("p1")).directions if d.merged_from)
    assert merged.big_idea == a.big_idea  # picked from A
    assert merged.copy.headline == b.copy.headline  # granular pick honored from B
