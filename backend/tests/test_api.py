"""API + SSE contract tests (Stage 03 Slice B, §16).

Exercises the project lifecycle over the real ``app.main:app`` via TestClient:
create -> list -> start (runs to the strategy gate) -> gate reject/approve, plus
the SSE event stream (backfill via Last-Event-ID, ordering, event-type coverage).

Keyless-first: the app boots and the whole pipeline runs on the deterministic
mock with ZERO provider keys.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from fastapi.testclient import TestClient

from app.main import app


BRIEF_BODY = {
    "brief": "Launch a sustainable sneaker brand for urban runners who care about the planet.",
    "brand_name": "Tread",
    "audience": "urban runners",
    "constraints": ["recycled materials only"],
}


@pytest.fixture
def client(clean_env):
    # Context-manager form triggers the lifespan (storage + graph saver + RunManager).
    with TestClient(app) as c:
        yield c


def _create_started_project(client) -> str:
    r = client.post("/api/projects", json=BRIEF_BODY)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r = client.post(f"/api/projects/{pid}/start")
    assert r.status_code == 202, r.text
    return pid


def test_create_and_list(client) -> None:
    r = client.post("/api/projects", json=BRIEF_BODY)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert pid

    r = client.get("/api/projects")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert pid in ids


def test_start_reaches_strategy_gate(client) -> None:
    pid = _create_started_project(client)

    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "awaiting_strategy_approval"
    assert body["interrupt"] is not None
    assert body["interrupt"]["gate"] == "strategy"
    assert body["strategy"] is not None


def test_cancel_marks_project_cancelled(client) -> None:
    pid = _create_started_project(client)  # awaiting_strategy_approval
    r = client.post(f"/api/projects/{pid}/cancel")
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "cancelled"
    # idempotent
    assert client.post(f"/api/projects/{pid}/cancel").json()["state"] == "cancelled"


def test_retry_conflicts_when_not_errored(client) -> None:
    pid = _create_started_project(client)  # not in an error state
    assert client.post(f"/api/projects/{pid}/retry").status_code == 409


def test_get_missing_project_404(client) -> None:
    assert client.get("/api/projects/does-not-exist").status_code == 404


def test_gate_reject_then_reinterrupt_and_wrong_state_409(client) -> None:
    pid = _create_started_project(client)

    r = client.post(
        f"/api/projects/{pid}/gates/strategy",
        json={"action": "reject", "notes": "sharper"},
    )
    assert r.status_code == 200, r.text
    # Reject re-runs strategize and returns to the gate.
    assert client.get(f"/api/projects/{pid}").json()["state"] == "awaiting_strategy_approval"

    # A gate call against a project NOT awaiting that gate returns 409.
    r2 = client.post("/api/projects", json=BRIEF_BODY)
    fresh = r2.json()["id"]  # intake, never started -> not awaiting
    conflict = client.post(
        f"/api/projects/{fresh}/gates/strategy",
        json={"action": "approve"},
    )
    assert conflict.status_code == 409, conflict.text


def test_gate_approve_fans_out_to_curation(client) -> None:
    pid = _create_started_project(client)

    r = client.post(
        f"/api/projects/{pid}/gates/strategy",
        json={"action": "approve"},
    )
    assert r.status_code == 200, r.text

    body = client.get(f"/api/projects/{pid}").json()
    # approval fans out and pauses at Gate 2 (sub-plan 04), not straight to done.
    assert body["state"] == "awaiting_curation"
    assert body["verbal_identity"] is not None
    assert body["creative_brief"] is not None
    assert body["territories"]
    assert body["interrupt"]["gate"] == "curation"
    assert body["directions"]  # K directions produced


def test_gate_approve_with_valid_edits_applies_and_completes(client) -> None:
    pid = _create_started_project(client)

    r = client.post(
        f"/api/projects/{pid}/gates/strategy",
        json={"action": "approve", "edits": {"positioning": "Radical proof over promises"}},
    )
    assert r.status_code == 200, r.text

    body = client.get(f"/api/projects/{pid}").json()
    assert body["state"] == "awaiting_curation"
    # the inline edit was applied to the checkpointed strategy (survives fan-out)
    assert body["strategy"]["positioning"] == "Radical proof over promises"


def test_gate_approve_with_invalid_edits_returns_422(client) -> None:
    pid = _create_started_project(client)

    r = client.post(
        f"/api/projects/{pid}/gates/strategy",
        json={"action": "approve", "edits": {"positioning": 12345}},  # int for a str field
    )
    assert r.status_code == 422, r.text
    # rejected at the boundary: the run did not advance and state is uncorrupted
    assert client.get(f"/api/projects/{pid}").json()["state"] == "awaiting_strategy_approval"


def _parse_sse(text: str) -> list[dict]:
    """Parse an SSE payload into a list of {id, event, data} frames."""
    frames: list[dict] = []
    cur: dict = {}
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line == "":
            if cur:
                frames.append(cur)
                cur = {}
            continue
        if line.startswith(":"):  # comment / heartbeat
            continue
        if line.startswith("id:"):
            cur["id"] = int(line[3:].strip())
        elif line.startswith("event:"):
            cur["event"] = line[6:].strip()
        elif line.startswith("data:"):
            cur["data"] = line[5:].strip()
    if cur:
        frames.append(cur)
    return frames


async def _drive_sse(app, pid: str, last_event_id: int, via_query: bool = False) -> tuple[int, str, str]:
    """Drive the SSE route at the ASGI level and return (status, ctype, body).

    Starlette's in-process transports buffer a response body to completion
    before exposing it, so an unbounded SSE generator would hang any TestClient
    read. Instead we invoke the app as an ASGI callable with a ``receive`` that
    signals ``http.disconnect`` shortly after the request is delivered: the
    generator's real production exit path (``is_disconnected()``) fires, so the
    backfill is captured without blocking on the live heartbeat tail.

    ``via_query`` sends the resume cursor as ``?lastEventId=`` (what the frontend's
    re-created EventSource uses) instead of the ``Last-Event-ID`` header.
    """
    path = f"/api/projects/{pid}/events"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": f"lastEventId={last_event_id}".encode() if via_query else b"",
        "root_path": "",
        "scheme": "http",
        "headers": [] if via_query else [(b"last-event-id", str(last_event_id).encode())],
        "server": ("testserver", 80),
        "client": ("test", 12345),
    }
    status = {"code": 0, "headers": []}
    chunks: list[bytes] = []

    async def receive():
        # Deliver the (empty) request body, then disconnect after the backfill
        # has been synchronously flushed by the generator.
        await asyncio.sleep(0.3)
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
            status["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body" and message.get("body"):
            chunks.append(message["body"])

    await app(scope, receive, send)
    ctype = ""
    for k, v in status["headers"]:
        if k.lower() == b"content-type":
            ctype = v.decode()
    return status["code"], ctype, b"".join(chunks).decode()


def _read_backfill(client, pid: str, last_event_id: int, via_query: bool = False) -> list[dict]:
    """Collect the SSE backfill frames for ``pid`` (see ``_drive_sse``)."""
    status, ctype, body = asyncio.run(_drive_sse(client.app, pid, last_event_id, via_query))
    assert status == 200
    assert ctype.startswith("text/event-stream")
    return _parse_sse(body)


def test_sse_backfill_ordering_and_types(client) -> None:
    pid = _create_started_project(client)

    frames = _read_backfill(client, pid, 0)
    ids = [f["id"] for f in frames if "id" in f]
    assert ids, "expected at least one backfilled event"
    # ids strictly increasing (ascending seq).
    assert all(b > a for a, b in zip(ids, ids[1:]))

    types = {f.get("event") for f in frames}
    assert {"run_created", "run_state_changed", "gate_reached"} <= types

    # data is valid JSON for a typed frame.
    typed = next(f for f in frames if f.get("event") == "gate_reached")
    payload = json.loads(typed["data"])
    assert payload.get("gate") == "strategy"


def test_sse_last_event_id_backfills_only_later(client) -> None:
    pid = _create_started_project(client)

    all_frames = _read_backfill(client, pid, 0)
    all_ids = [f["id"] for f in all_frames if "id" in f]
    assert len(all_ids) >= 2
    mid = all_ids[len(all_ids) // 2]

    later = _read_backfill(client, pid, mid)
    later_ids = [f["id"] for f in later if "id" in f]
    assert later_ids  # there are later events
    assert all(i > mid for i in later_ids)


def test_sse_gate_resolved_after_approve(client) -> None:
    pid = _create_started_project(client)
    client.post(f"/api/projects/{pid}/gates/strategy", json={"action": "approve"})

    frames = _read_backfill(client, pid, 0)
    types = [f.get("event") for f in frames]
    assert "gate_resolved" in types
    assert "run_state_changed" in types


def test_sse_resume_via_query_param(client) -> None:
    pid = _create_started_project(client)
    all_ids = [f["id"] for f in _read_backfill(client, pid, 0) if "id" in f]
    assert len(all_ids) >= 2
    mid = all_ids[len(all_ids) // 2]

    # the frontend's re-created EventSource sends ?lastEventId= (not the header);
    # the backend must resume from it, not replay the whole log from seq 0.
    later = _read_backfill(client, pid, mid, via_query=True)
    later_ids = [f["id"] for f in later if "id" in f]
    assert later_ids and all(i > mid for i in later_ids)
