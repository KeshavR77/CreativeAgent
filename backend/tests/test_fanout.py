"""Fan-out, critic & divergence contract tests (Stage 04, §16).

Drives the RunManager through Gate-1 approval into the parallel `Send` fan-out:
K territory-seeded directions, each independently critiqued and divergence-scored,
land via the `upsert_directions` reducer. A failing branch is isolated to
`failed_territories` and the run continues to the curation gate.
"""

from __future__ import annotations

import threading

import pytest_asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.config import get_settings
from app.graph import exploration
from app.graph.runner import RunManager
from app.models.artifacts import Brief
from app.models.events import RunState
from app.storage.db import init_db, make_engine, make_sessionmaker
from app.storage.repo import EventBus, EventRepo, RegistryRepo

BRIEF = Brief(
    brief="Launch a sustainable sneaker brand for runners sick of greenwashing.",
    brand_name="",
    audience="runners frustrated by greenwashing",
    constraints=[],
)


@pytest_asyncio.fixture
async def manager(tmp_path, clean_env):
    engine = make_engine(f"sqlite:///{tmp_path}/app.sqlite")
    init_db(engine)
    sm = make_sessionmaker(engine)
    bus = EventBus()
    registry = RegistryRepo(sm)
    events = EventRepo(sm, bus)
    async with AsyncSqliteSaver.from_conn_string(f"{tmp_path}/graph.sqlite") as saver:
        yield RunManager(registry, events, bus, saver), registry


async def _drive_to_curation(rm, pid: str = "p1") -> None:
    await (await rm.start(pid, BRIEF))
    await (await rm.resume(pid, {"action": "approve"}))


async def test_fanout_directions_are_critiqued_and_scored(manager) -> None:
    rm, registry = manager
    await _drive_to_curation(rm)

    assert registry.get("p1").state == RunState.awaiting_curation.value
    view = await rm.get_view("p1")

    assert len(view.directions) == get_settings().K  # all K territories landed via the reducer
    for d in view.directions:
        assert d.critique is not None
        assert d.critique.verdict in ("ship", "revise", "kill")
        assert len(d.critique.case_against.split()) >= 50  # >=50-word case_against
        assert d.brain == "mock"  # keyless -> truthful brain (not "conceptial")
        assert d.divergence_score is not None
        assert d.sketches  # non-empty sketches (placeholders under keyless)
        assert d.art_direction.moodboard  # non-empty moodboard (placeholders under keyless)

    assert view.divergence is not None
    assert set(view.divergence) >= {"min", "mean", "warning"}


async def test_fanout_failed_branch_isolated_run_continues(manager, monkeypatch) -> None:
    rm, registry = manager

    # Fail exactly the first branch to reach the ideator; the rest succeed.
    original = exploration.ideate_one
    lock = threading.Lock()
    failed_once = {"done": False}

    def flaky_ideate(project_id, territory, **kwargs):
        with lock:
            if not failed_once["done"]:
                failed_once["done"] = True
                raise ValueError("simulated ideator failure")
        return original(project_id, territory, **kwargs)

    monkeypatch.setattr(exploration, "ideate_one", flaky_ideate)

    await _drive_to_curation(rm)

    # the run survives the failed branch and still reaches Gate 2
    assert registry.get("p1").state == RunState.awaiting_curation.value
    snap = await rm.graph.aget_state({"configurable": {"thread_id": "p1"}})
    values = snap.values
    k = get_settings().K
    assert len(values.get("failed_territories", [])) == 1  # exactly one branch failed
    survivors = values.get("directions", [])
    assert len(survivors) == k - 1  # the rest landed
    # K-1 >= 2 survivors, so divergence still scores every one of them
    assert all(d.divergence_score is not None for d in survivors)


async def test_fanout_moodboard_is_hybrid_when_both_lanes_enabled(manager, clean_env) -> None:
    rm, _ = manager
    clean_env.setenv("IMAGE_GEN_PROVIDER", "mock")
    clean_env.setenv("IMAGE_SOURCE_PROVIDER", "pexels")

    await _drive_to_curation(rm)
    view = await rm.get_view("p1")

    # at least one direction's moodboard mixes generated + sourced tiles (hybrid)
    assert any(
        {"generated", "sourced"} <= {img.kind for img in d.art_direction.moodboard}
        for d in view.directions
    )
    # with the gen lane on, sketches are actually generated (not placeholders)
    assert all(all(s.kind == "generated" for s in d.sketches) for d in view.directions)
