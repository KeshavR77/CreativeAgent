"""Conceptial ideator client tests (Stage 07, §8.3/§16).

Keyless the client is unavailable (node falls back to claude_high_temp/mock). When
configured it POSTs one ``{prompt, seed}`` body per idea to ``/generate`` with Bearer
auth (matching BrainstormLM's `creativity_steering` serving harness) — all exercised
in-process via an httpx MockTransport (no network, no real keys).
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.conceptial import ConceptialUnavailable, generate


def test_unavailable_when_keyless(clean_env) -> None:
    with pytest.raises(ConceptialUnavailable):
        generate("a brief", {"label": "T", "lens": "l"})


def test_generate_posts_prompt_and_parses_title_notes(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"text": "Title: trace the seams\nNotes: bold"})

    client = httpx.Client(base_url="http://conceptial.test", transport=httpx.MockTransport(handler))
    ideas = generate("brief text", {"label": "Radical", "lens": "proof"}, n_ideas=1, client=client)

    assert ideas == [{"big_idea": "trace the seams", "notes": "bold"}]
    assert captured["url"].endswith("/generate")
    assert captured["body"]["seed"] == 0
    assert "brief text" in captured["body"]["prompt"]
    assert "Radical" in captured["body"]["prompt"]
    assert "proof" in captured["body"]["prompt"]


def test_generate_n_ideas_issues_one_call_per_idea_with_distinct_seeds(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    seeds_seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seeds_seen.append(body["seed"])
        return httpx.Response(200, json={"text": f"Title: idea {body['seed']}\nNotes: n"})

    client = httpx.Client(base_url="http://conceptial.test", transport=httpx.MockTransport(handler))
    ideas = generate("brief", {"label": "T", "lens": "l"}, n_ideas=3, client=client)

    assert seeds_seen == [0, 1, 2]
    assert [i["big_idea"] for i in ideas] == ["idea 0", "idea 1", "idea 2"]


def test_generate_forwards_configured_variant(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    clean_env.setenv("CONCEPTIAL_VARIANT", "bracket")
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"text": "Title: x\nNotes: "})

    client = httpx.Client(base_url="http://conceptial.test", transport=httpx.MockTransport(handler))
    generate("brief", {"label": "T", "lens": "l"}, client=client)
    assert captured["body"]["variant"] == "bracket"


def test_generate_falls_back_to_raw_text_when_unformatted(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "just a freeform completion"})

    client = httpx.Client(base_url="http://conceptial.test", transport=httpx.MockTransport(handler))
    ideas = generate("brief", {"label": "T", "lens": "l"}, client=client)
    assert ideas == [{"big_idea": "just a freeform completion", "notes": ""}]


def test_bearer_auth_header_set_when_keyed(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")
    clean_env.setenv("CONCEPTIAL_API_KEY", "conceptial-secret")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"text": "Title: x\nNotes: "})

    # transport injection exercises the real client-construction path (auth header).
    generate("b", {"label": "T", "lens": "l"}, transport=httpx.MockTransport(handler))
    assert seen["auth"] == "Bearer conceptial-secret"


def test_no_auth_header_without_key(clean_env) -> None:
    clean_env.setenv("CONCEPTIAL_BASE_URL", "http://conceptial.test")  # no API key
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"text": "Title: x\nNotes: "})

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
        return httpx.Response(200, json={"text": "Title: y\nNotes: "})

    generate("b", Territory(label="Transparency", lens="proof"), transport=httpx.MockTransport(handler))
    assert "Transparency" in captured["body"]["prompt"]
    assert "proof" in captured["body"]["prompt"]


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


def test_ideate_llm_brain_reflects_configured_provider(clean_env, monkeypatch) -> None:
    """The LLM ideator labels `brain` provider-agnostically: the mock -> 'mock',
    any real model -> the configured IDEATOR_FALLBACK. So swapping get_chat_model to
    GLM (IDEATOR_FALLBACK='glm') labels the stage truthfully, not as Claude."""
    from app.graph import exploration
    from app.models.artifacts import Territory
    from app.services.mock_chat import MockChatModel

    clean_env.setenv("IDEATOR_FALLBACK", "glm")  # no conceptial -> LLM ideator path
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
