"""Storage-layer contract tests (Stage 02, §7/§16).

Registry CRUD + `list_resumable` filtering; event-log append atomicity, per-project
seq uniqueness, `since()` ordering; in-process pub/sub delivery. Repos stay narrow
so a Postgres backend can swap in later.
"""

from __future__ import annotations

import pytest

from app.models.events import RunState
from app.storage.db import init_db, make_engine, make_sessionmaker
from app.storage.repo import EventBus, EventRepo, RegistryRepo


@pytest.fixture
def stores(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    sm = make_sessionmaker(engine)
    bus = EventBus()
    return RegistryRepo(sm), EventRepo(sm, bus), bus


# --------------------------------------------------------------------------- #
# RegistryRepo                                                                #
# --------------------------------------------------------------------------- #
def test_registry_create_get(stores) -> None:
    reg, _, _ = stores
    created = reg.create("p1", state=RunState.researching, brief_excerpt="Launch a shoe")
    assert created.id == "p1"
    assert created.state == "researching"
    got = reg.get("p1")
    assert got.state == "researching"
    assert got.brief_excerpt == "Launch a shoe"


def test_registry_create_defaults_to_intake(stores) -> None:
    reg, _, _ = stores
    assert reg.create("p1").state == "intake"


def test_registry_get_missing_returns_none(stores) -> None:
    reg, _, _ = stores
    assert reg.get("nope") is None


def test_registry_list(stores) -> None:
    reg, _, _ = stores
    reg.create("p1")
    reg.create("p2")
    assert {p.id for p in reg.list()} == {"p1", "p2"}


def test_registry_update_state_and_error(stores) -> None:
    reg, _, _ = stores
    reg.create("p1", state=RunState.researching)
    reg.update_state("p1", RunState.error, error="boom")
    got = reg.get("p1")
    assert got.state == "error"
    assert got.error == "boom"


def test_list_resumable_filters_excluded_states(stores) -> None:
    reg, _, _ = stores
    reg.create("running", state=RunState.researching)
    reg.create("errored", state=RunState.error)
    reg.create("gate1", state=RunState.awaiting_strategy_approval)
    reg.create("gate2", state=RunState.awaiting_curation)
    reg.create("finished", state=RunState.done)
    reg.create("cancelled", state=RunState.cancelled)
    reg.create("fresh", state=RunState.intake)
    resumable = {p.id for p in reg.list_resumable()}
    # only actively-running or crashed runs resume; gated/terminal/fresh do not.
    assert resumable == {"running", "errored"}


# --------------------------------------------------------------------------- #
# EventRepo — append / seq / since                                            #
# --------------------------------------------------------------------------- #
def test_event_append_returns_contiguous_seq(stores) -> None:
    reg, events, _ = stores
    reg.create("p1")
    seqs = [events.append("p1", "agent_started", {"i": i}) for i in range(5)]
    assert seqs == [1, 2, 3, 4, 5]


def test_event_seq_is_per_project(stores) -> None:
    reg, events, _ = stores
    reg.create("p1")
    reg.create("p2")
    assert events.append("p1", "x", {}) == 1
    assert events.append("p1", "x", {}) == 2
    assert events.append("p2", "x", {}) == 1  # independent sequence
    assert events.append("p2", "x", {}) == 2


def test_event_since_ordering(stores) -> None:
    reg, events, _ = stores
    reg.create("p1")
    for i in range(4):
        events.append("p1", "t", {"i": i})
    after = events.since("p1", 2)
    assert [e.seq for e in after] == [3, 4]
    assert after[0].payload == {"i": 2}


def test_event_append_many_unique_seq(stores) -> None:
    reg, events, _ = stores
    reg.create("p1")
    seqs = [events.append("p1", "t", {}) for _ in range(20)]
    assert seqs == list(range(1, 21))
    assert len(set(seqs)) == 20


# --------------------------------------------------------------------------- #
# pub/sub                                                                     #
# --------------------------------------------------------------------------- #
def test_pubsub_delivers_appended_event(stores) -> None:
    reg, events, bus = stores
    reg.create("p1")
    q = bus.subscribe("p1")
    seq = events.append("p1", "artifact_written", {"artifact": "strategy"})
    ev = q.get_nowait()
    assert ev["seq"] == seq
    assert ev["type"] == "artifact_written"
    assert ev["payload"] == {"artifact": "strategy"}


def test_pubsub_is_scoped_per_project(stores) -> None:
    reg, events, bus = stores
    reg.create("p1")
    reg.create("p2")
    q1 = bus.subscribe("p1")
    events.append("p2", "t", {})
    assert q1.empty()  # p2's event must not reach p1's subscriber
