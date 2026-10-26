"""Graph-spine contract tests.

Drives the ``RunManager`` directly against a tmp_path SQLite registry/event log
and a real ``AsyncSqliteSaver`` checkpointer. Proves the walking skeleton:
brief -> research -> strategize -> strategy_gate (human interrupt) -> verbal ->
briefwrite -> seed -> END, with approve/reject routing and durable checkpointing.

Keyless-first: every model call resolves to the deterministic mock (empty env),
so these assertions hold with ZERO provider keys.
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.build import build_graph
from app.graph.runner import RunManager
from app.models.artifacts import Brief
from app.models.events import RunState
from app.storage.db import init_db, make_engine, make_sessionmaker
from app.storage.repo import EventBus, EventRepo, RegistryRepo


SNEAKER_BRIEF = Brief(
    brief="Launch a sustainable sneaker brand for urban runners who care about the planet.",
    brand_name="Tread",
    audience="urban runners",
    constraints=["recycled materials only"],
)


@pytest_asyncio.fixture
async def manager(tmp_path, clean_env):
    """A live RunManager over tmp_path storage + an open AsyncSqliteSaver."""
    engine = make_engine(f"sqlite:///{tmp_path}/app.sqlite")
    init_db(engine)
    sm = make_sessionmaker(engine)
    bus = EventBus()
    registry = RegistryRepo(sm)
    events = EventRepo(sm, bus)
    async with AsyncSqliteSaver.from_conn_string(f"{tmp_path}/graph.sqlite") as saver:
        yield RunManager(registry, events, bus, saver), registry, tmp_path


async def test_start_pauses_at_strategy_gate(manager) -> None:
    rm, registry, _ = manager
    task = await rm.start("p1", SNEAKER_BRIEF)
    await task

    assert registry.get("p1").state == RunState.awaiting_strategy_approval.value

    view = await rm.get_view("p1")
    assert view is not None
    assert view.interrupt is not None
    assert view.interrupt.get("gate") == "strategy"

    # research + strategy produced and checkpointed BY the time we hit the gate.
    assert view.strategy is not None
    snap = await rm.graph.aget_state({"configurable": {"thread_id": "p1"}})
    assert snap.values.get("research") is not None
    assert snap.values.get("strategy") is not None


async def test_approve_fans_out_to_curation_gate(manager) -> None:
    rm, registry, _ = manager
    await (await rm.start("p1", SNEAKER_BRIEF))

    task = await rm.resume("p1", {"action": "approve"})
    await task

    # Gate-1 approval runs verbal/briefwrite/seed, then fans out and pauses at
    # Gate 2 (curation) — no longer straight to END.
    assert registry.get("p1").state == RunState.awaiting_curation.value

    view = await rm.get_view("p1")
    assert view.verbal_identity is not None
    assert view.creative_brief is not None
    assert view.territories  # non-empty
    assert view.interrupt is not None
    assert view.interrupt.get("gate") == "curation"


async def test_reject_reinterrupts_with_notes(manager) -> None:
    rm, registry, _ = manager
    await (await rm.start("p1", SNEAKER_BRIEF))

    task = await rm.resume("p1", {"action": "reject", "notes": "sharper"})
    await task

    # Rejection re-runs strategize and pauses at the gate again.
    assert registry.get("p1").state == RunState.awaiting_strategy_approval.value
    snap = await rm.graph.aget_state({"configurable": {"thread_id": "p1"}})
    assert snap.values.get("rejection_notes") == "sharper"
    view = await rm.get_view("p1")
    assert view.interrupt is not None
    assert view.interrupt.get("gate") == "strategy"


async def test_checkpointer_persists_across_fresh_graph(manager, tmp_path) -> None:
    rm, registry, mgr_tmp = manager
    await (await rm.start("p1", SNEAKER_BRIEF))

    cfg = {"configurable": {"thread_id": "p1"}}
    # Exit the manager's saver by opening a BRAND-NEW saver on the SAME file and
    # a fresh graph instance; the accumulated state must still be there.
    async with AsyncSqliteSaver.from_conn_string(f"{mgr_tmp}/graph.sqlite") as saver2:
        graph2 = build_graph(saver2)
        snap = await graph2.aget_state(cfg)
        values = snap.values
        assert values.get("brief") is not None
        assert values.get("research") is not None
        assert values.get("strategy") is not None
