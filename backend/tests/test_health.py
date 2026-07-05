"""Empty-environment /api/health contract (Stage 01, §4/§7)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _fresh_client() -> TestClient:
    # Import lazily so env clearing (via clean_env) happens before app import.
    from app.main import app

    return TestClient(app)


def test_health_empty_env_exact_payload(clean_env) -> None:
    client = _fresh_client()
    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")

    assert resp.json() == {
        "status": "ok",
        "providers": {
            "claude": "mock",
            "conceptial": "mock",
            "search": "mock",
            "embeddings": "mock",
        },
        "image_gen": {"enabled": False, "provider": None},
        "image_source": {"enabled": False, "provider": None},
        "tracing": False,
    }
