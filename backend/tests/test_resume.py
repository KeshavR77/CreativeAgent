"""Hardening: restart-resilience, retry, cancel, gate purity (Stage 09, §16).

A "restart" is modeled by building a FRESH RunManager (new checkpointer) on the
SAME on-disk registry/event/graph DBs — exactly what a new process sees. State is
durable, so the run picks up where it left off.
"""

from __future__ import annotations

import contextlib

import pytest_asyncio

from app.graph.runner import RunManager
from app.storage.checkpoint import open_checkpointer
from app.models.artifacts import Brief
from app.models.events import RunState
from app.storage.db import init_db, make_engine, make_sessionmaker
from app.storage.repo import EventBus, EventRepo, RegistryRepo

BRIEF = Brief(
    brief="Launch a sustainable sneaker brand for runners sick of greenwashing.",
    audience="runners",
)


@pytest_asyncio.fixture
async def restartable(tmp_path, clean_env):
    """Yields (make_manager, registry): a factory that builds a fresh RunManager on
    the SAME durable DBs (a process restart), plus the shared registry."""
    engine = make_engine(f"sqlite:///{tmp_path}/app.sqlite")
    init_db(engine)
    sm = make_sessionmaker(engine)
    registry = RegistryRepo(sm)
    bus = EventBus()
    events = EventRepo(sm, bus)
    graph_db = f"{tmp_path}/graph.sqlite"

    @contextlib.asynccontextmanager
    async def make_manager():
        async with open_checkpointer(graph_db) as saver:
            yield RunManager(registry, events, bus, saver)

    yield make_manager, registry


def _agent_completions(rm, pid, agent) -> int:
    return sum(
        1 for e in rm.events.since(pid, 0) if e.type == "agent_completed" and e.payload.get("agent") == agent
    )


async def test_gate2_state_intact_after_restart(restartable):
    make_manager, registry = restartable
    async with make_manager() as rm:
        await (await rm.start("p1", BRIEF))
        await (await rm.resume("p1", {"action": "approve"}))
        assert registry.get("p1").state == RunState.awaiting_curation.value
        did = (await rm.get_view("p1")).directions[0].id

    # --- simulate a process restart: fresh RunManager on the SAME DBs ---
    async with make_manager() as rm2:
        view = await rm2.get_view("p1")
        assert view.state == RunState.awaiting_curation.value  # cockpit intact
        assert view.directions and view.interrupt["gate"] == "curation"
        # curation ops + finalize still work after the restart
        await (await rm2.resume("p1", {"op": "promote", "direction_id": did}))
        await (await rm2.resume("p1", {"op": "finalize"}))
        assert registry.get("p1").state == RunState.done.value
        assert (await rm2.get_view("p1")).packages


async def test_retry_resumes_an_errored_run(restartable, monkeypatch):
    make_manager, registry = restartable
    from app.graph import build as build_mod
    from app.graph import nodes as nodes_mod

    state = {"n": 0}
    original = nodes_mod.research

    def flaky_research(s):
        state["n"] += 1
        if state["n"] == 1:
            raise ValueError("boom (non-transient -> run errors)")
        return original(s)

    monkeypatch.setattr(build_mod, "research", flaky_research)  # picked up when the graph is built

    async with make_manager() as rm:
        await (await rm.start("p1", BRIEF))
        assert registry.get("p1").state == RunState.error.value  # errored on the first research

        task = await rm.retry("p1")
        assert task is not None
        await task
        # resumed from the checkpoint: research re-ran and the run reached Gate 1
        assert state["n"] == 2
        assert registry.get("p1").state == RunState.awaiting_strategy_approval.value


async def test_retry_rejected_when_not_errored(restartable):
    make_manager, _ = restartable
    async with make_manager() as rm:
        await (await rm.start("p1", BRIEF))  # awaiting_strategy_approval, not error
        assert await rm.retry("p1") is None


async def test_cancel_marks_cancelled_and_is_terminal(restartable):
    make_manager, registry = restartable
    async with make_manager() as rm:
        await (await rm.start("p1", BRIEF))
        assert registry.get("p1").state == RunState.awaiting_strategy_approval.value

        assert await rm.cancel("p1") is True
        assert registry.get("p1").state == RunState.cancelled.value
        assert "run_cancelled" in {e.type for e in rm.events.since("p1", 0)}
        # cancelled is terminal — not picked up by boot recovery
        assert "p1" not in {r.id for r in registry.list_resumable()}


async def test_gate_reentry_does_not_rerun_completed_nodes(restartable):
    """Gate purity: resuming through the gate must not re-run the pre-gate nodes
    (no duplicated events/writes/provider calls — idempotency via the checkpoint)."""
    make_manager, _ = restartable
    async with make_manager() as rm:
        await (await rm.start("p1", BRIEF))
        assert _agent_completions(rm, "p1", "research") == 1

        await (await rm.resume("p1", {"action": "approve"}))
        assert _agent_completions(rm, "p1", "research") == 1  # research ran exactly once
