"""External ideator client tests.

Keyless the client is unavailable (node falls back to claude_high_temp/mock). When
configured it POSTs the structured body to ``/generate`` with Bearer auth — all
exercised in-process via an httpx MockTransport (no network, no real keys).
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.ideator import IdeatorUnavailable, generate


def test_unavailable_when_keyless(clean_env) -> None:
    with pytest.raises(IdeatorUnavailable):
        generate("a brief", {"label": "T", "lens": "l"})


def test_generate_posts_structured_body_and_parses(clean_env) -> None:
    clean_env.setenv("IDEATOR_BASE_URL", "http://ideator.test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ideas": [{"big_idea": "trace the seams", "notes": "bold"}]})

    client = httpx.Client(base_url="http://ideator.test", transport=httpx.MockTransport(handler))
    ideas = generate("brief text", {"label": "Radical", "lens": "proof"}, n_ideas=1, client=client)

    assert ideas == [{"big_idea": "trace the seams", "notes": "bold"}]
    assert captured["url"].endswith("/generate")
    assert captured["body"]["creative_brief"] == "brief text"
    assert captured["body"]["territory"] == {"label": "Radical", "lens": "proof"}
    assert captured["body"]["n_ideas"] == 1


def test_bearer_auth_header_set_when_keyed(clean_env) -> None:
    clean_env.setenv("IDEATOR_BASE_URL", "http://ideator.test")
    clean_env.setenv("IDEATOR_API_KEY", "ideator-secret")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ideas": [{"big_idea": "x", "notes": ""}]})

    # transport injection exercises the real client-construction path (auth header).
    generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))
    assert seen["auth"] == "Bearer ideator-secret"


def test_no_auth_header_without_key(clean_env) -> None:
    clean_env.setenv("IDEATOR_BASE_URL", "http://ideator.test")  # no API key
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"ideas": [{"big_idea": "x", "notes": ""}]})

    generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))
    assert seen["auth"] is None


def test_server_error_raises_unavailable(clean_env) -> None:
    clean_env.setenv("IDEATOR_BASE_URL", "http://ideator.test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    with pytest.raises(IdeatorUnavailable):
        generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))


def test_accepts_territory_object(clean_env) -> None:
    from app.models.artifacts import Territory

    clean_env.setenv("IDEATOR_BASE_URL", "http://ideator.test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ideas": [{"big_idea": "y", "notes": ""}]})

    generate("b", Territory(label="Transparency", lens="proof"), transport=httpx.MockTransport(handler))
    assert captured["body"]["territory"] == {"label": "Transparency", "lens": "proof"}


def test_ideate_falls_back_with_truthful_brain_when_ideator_fails(clean_env, monkeypatch) -> None:
    """Ideator configured but failing -> ideate_one falls back and records `brain`
    truthfully (keyless claude -> 'mock', never 'external_ideator' for a fallback)."""
    from app.graph import exploration
    from app.models.artifacts import Territory

    clean_env.setenv("IDEATOR_BASE_URL", "http://ideator.test")  # ideator resolves "real"

    def _boom(*args, **kwargs):
        raise IdeatorUnavailable("down")

    monkeypatch.setattr(exploration, "ideator_generate", _boom)
    _big_idea, brain = exploration.ideate_one("p1", Territory(label="Radical", lens="proof"))
    assert brain == "mock"


def test_ideate_llm_brain_reflects_configured_provider(clean_env, monkeypatch) -> None:
    """The LLM ideator labels `brain` provider-agnostically: the mock -> 'mock',
    any real model -> the configured IDEATOR_FALLBACK. So swapping get_chat_model to
    GLM (IDEATOR_FALLBACK='glm') labels the stage truthfully, not as Claude."""
    from app.graph import exploration
    from app.models.artifacts import Territory
    from app.services.mock_chat import MockChatModel

    clean_env.setenv("IDEATOR_FALLBACK", "glm")  # no external ideator -> LLM ideator path
    monkeypatch.setattr(exploration, "generate_structured", lambda *a, **k: exploration.IdeaResult(big_idea="a GLM idea"))

    class _RealModel:  # stand-in for a real ChatGLM/ChatAnthropic (i.e. not the mock)
        pass

    monkeypatch.setattr(exploration, "get_chat_model", lambda *a, **k: _RealModel())
    big_idea, brain = exploration.ideate_one("p1", Territory(label="Radical", lens="proof"))
    assert big_idea == "a GLM idea"
    assert brain == "glm"  # the configured provider label, not a hardcoded "claude_high_temp"

    monkeypatch.setattr(exploration, "get_chat_model", lambda *a, **k: MockChatModel(seed="s", role="ideator"))
    _idea2, brain2 = exploration.ideate_one("p1", Territory(label="Radical", lens="proof"))
    assert brain2 == "mock"  # the mock is always labelled truthfully
