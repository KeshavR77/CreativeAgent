"""Conceptial ideator client tests (Stage 07, §8.3/§16).

Keyless the client is unavailable (node falls back to claude_high_temp/mock). When
configured it POSTs the structured body to ``/generate`` with Bearer auth — all
exercised in-process via an httpx MockTransport (no network, no real keys).
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.conceptial import ConceptialUnavailable, generate


def test_unavailable_when_keyless(clean_env) -> None:
    with pytest.raises(ConceptialUnavailable):
        generate("a brief", {"label": "T", "lens": "l"})


def test_generate_posts_structured_body_and_parses(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ideas": [{"big_idea": "trace the seams", "notes": "bold"}]})

    client = httpx.Client(base_url="http://conceptial.test", transport=httpx.MockTransport(handler))
    ideas = generate("brief text", {"label": "Radical", "lens": "proof"}, n_ideas=1, client=client)

    assert ideas == [{"big_idea": "trace the seams", "notes": "bold"}]
    assert captured["url"].endswith("/generate")
    assert captured["body"]["creative_brief"] == "brief text"
    assert captured["body"]["territory"] == {"label": "Radical", "lens": "proof"}
    assert captured["body"]["n_ideas"] == 1


def test_bearer_auth_header_set_when_keyed(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    clean_env.setenv("CONCEPTIAL_API_KEY", "conceptial-secret")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ideas": [{"big_idea": "x", "notes": ""}]})

    # transport injection exercises the real client-construction path (auth header).
    generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))
    assert seen["auth"] == "Bearer conceptial-secret"


def test_no_auth_header_without_key(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")  # no API key
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ideas": [{"big_idea": "x", "notes": ""}]})

    generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))
    assert seen["auth"] is None


def test_server_error_raises_unavailable(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    with pytest.raises(ConceptialUnavailable):
        generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))


def test_accepts_territory_object(clean_env) -> None:
    from app.models.artifacts import Territory

    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ideas": [{"big_idea": "y", "notes": ""}]})

    generate("b", Territory(label="Transparency", lens="proof"), transport=httpx.MockTransport(handler))
    assert captured["body"]["territory"] == {"label": "Transparency", "lens": "proof"}


def test_ideate_falls_back_with_truthful_brain_when_conceptial_fails(clean_env, monkeypatch) -> None:
    """Conceptial configured but failing -> ideate_one falls back and records `brain`
    truthfully (keyless claude -> 'mock', never 'conceptial' for a fallback)."""
    from app.graph import exploration
    from app.models.artifacts import Territory

    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")  # conceptial resolves "real"

    def _boom(*args, **kwargs):
        raise ConceptialUnavailable("down")

    monkeypatch.setattr(exploration, "conceptial_generate", _boom)
    _big_idea, brain = exploration.ideate_one("p1", Territory(label="Radical", lens="proof"))
    assert brain == "mock"
