"""Curation-ops API tests.

Exercises the direction ops over the real app: 409 outside awaiting_curation,
edit validation (400 non-editable / 422 invalid value), promote/merge, the
divergence + packages reads, and finalize producing packages.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

BRIEF_BODY = {
    "brief": "Launch a sustainable sneaker brand for runners sick of greenwashing.",
    "audience": "runners",
}


@pytest.fixture
def client(clean_env):
    with TestClient(app) as c:
        yield c


def _to_curation(client) -> tuple[str, list]:
    pid = client.post("/api/projects", json=BRIEF_BODY).json()["id"]
    client.post(f"/api/projects/{pid}/start")
    assert client.post(f"/api/projects/{pid}/gates/strategy", json={"action": "approve"}).status_code == 200
    body = client.get(f"/api/projects/{pid}").json()
    assert body["state"] == "awaiting_curation"
    return pid, body["directions"]


def test_promote_via_api(client) -> None:
    pid, dirs = _to_curation(client)
    did = dirs[0]["id"]
    r = client.post(f"/api/projects/{pid}/directions/{did}/promote")
    assert r.status_code == 200, r.text
    d = next(x for x in r.json()["directions"] if x["id"] == did)
    assert d["status"] == "promoted"


def test_ops_409_outside_curation(client) -> None:
    # a freshly created (intake) project is not awaiting curation
    pid = client.post("/api/projects", json=BRIEF_BODY).json()["id"]
    assert client.post(f"/api/projects/{pid}/directions/x/promote").status_code == 409


def test_edit_validation(client) -> None:
    pid, dirs = _to_curation(client)
    did = dirs[0]["id"]
    # non-editable field -> 400
    assert client.post(
        f"/api/projects/{pid}/directions/{did}/edit", json={"field": "status", "value": "promoted"}
    ).status_code == 400
    # invalid value type for an editable field -> 422
    assert client.post(
        f"/api/projects/{pid}/directions/{did}/edit", json={"field": "big_idea", "value": 123}
    ).status_code == 422
    # valid edit -> 200
    r = client.post(
        f"/api/projects/{pid}/directions/{did}/edit",
        json={"field": "copy.headline", "value": "Nothing to hide."},
    )
    assert r.status_code == 200, r.text


def test_merge_and_divergence_read(client) -> None:
    pid, dirs = _to_curation(client)
    ids = [d["id"] for d in dirs[:2]]
    r = client.post(
        f"/api/projects/{pid}/directions/merge",
        json={"direction_ids": ids, "field_choices": {"big_idea": ids[0]}},
    )
    assert r.status_code == 200, r.text
    div = client.get(f"/api/projects/{pid}/divergence").json()
    assert "min" in div and "warning" in div


def test_finalize_produces_packages(client) -> None:
    pid, dirs = _to_curation(client)
    did = dirs[0]["id"]
    client.post(f"/api/projects/{pid}/directions/{did}/promote")
    r = client.post(f"/api/projects/{pid}/finalize", json={})
    assert r.status_code == 200, r.text

    assert client.get(f"/api/projects/{pid}").json()["state"] == "done"
    packages = client.get(f"/api/projects/{pid}/packages").json()
    assert packages
    assert packages[0]["direction_id"] == did


def test_regenerate_sketch_endpoint_is_wired(client) -> None:
    pid, dirs = _to_curation(client)
    did = dirs[0]["id"]
    r = client.post(f"/api/projects/{pid}/directions/{did}/regenerate_sketch", json={"index": 0})
    assert r.status_code == 200, r.text
    # visual regen keeps the run at the curation gate (no state advance)
    assert client.get(f"/api/projects/{pid}").json()["state"] == "awaiting_curation"


def test_regenerate_endpoints_409_outside_curation(client) -> None:
    pid = client.post("/api/projects", json=BRIEF_BODY).json()["id"]  # intake, not awaiting curation
    assert client.post(f"/api/projects/{pid}/directions/x/regenerate_sketches").status_code == 409


def test_export_and_token_endpoints(client) -> None:
    pid, dirs = _to_curation(client)
    did = dirs[0]["id"]
    client.post(f"/api/projects/{pid}/directions/{did}/promote")
    client.post(f"/api/projects/{pid}/finalize", json={})

    r = client.get(f"/api/projects/{pid}/export.md")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/markdown")
    assert "## AI disclosure" in r.text

    r = client.get(f"/api/projects/{pid}/tokens.json")
    assert r.status_code == 200
    assert "color" in r.json()

    r = client.get(f"/api/projects/{pid}/tokens.css")
    assert r.status_code == 200
    assert ":root {" in r.text

    # ?direction_id= filtering works
    assert client.get(f"/api/projects/{pid}/export.md?direction_id={did}").status_code == 200


def test_export_404_before_finalize(client) -> None:
    pid, _ = _to_curation(client)  # awaiting_curation, no packages yet
    assert client.get(f"/api/projects/{pid}/export.md").status_code == 404
